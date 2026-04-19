"""NER на базе Natasha — для уверенной детекции ФИО, локаций (адресов) и дат."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ..types import PIICategory
from .base import RawMatch

# Ленивая инициализация — модели Natasha занимают ~150 МБ ОЗУ
_NER_BUNDLE: dict[str, Any] | None = None

# Регулярки для фильтрации ложных срабатываний (OCR-мусор и английские тексты)
_LATIN_RE = re.compile(r"[a-zA-Z]")
_RUS_VOWEL_RE = re.compile(r"[аеёиоуыэюяАЕЁИОУЫЭЮЯ]")

_MIN_NER_TEXT_LEN = 50    # Слишком короткий текст — никаких сущностей там нет
_MIN_CYR_RATIO = 0.05     # Менее 5% кириллицы → не русский текст, NER бесполезен


def _bundle() -> dict[str, Any] | None:
    global _NER_BUNDLE
    if _NER_BUNDLE is not None:
        return _NER_BUNDLE
    try:
        from natasha import (
            Doc,
            MorphVocab,
            NamesExtractor,
            NewsEmbedding,
            NewsMorphTagger,
            NewsNERTagger,
            Segmenter,
        )
    except ImportError:
        return None

    embedding = NewsEmbedding()
    _NER_BUNDLE = {
        "Doc": Doc,
        "segmenter": Segmenter(),
        "morph_tagger": NewsMorphTagger(embedding),
        "ner_tagger": NewsNERTagger(embedding),
        "morph_vocab": MorphVocab(),
        "names_extractor": NamesExtractor(MorphVocab()),
    }
    return _NER_BUNDLE


def detect_ner(text: str, max_chars: int = 20_000) -> Iterable[RawMatch]:
    """Извлечь сущности через Natasha. На больших текстах — нарезаем чанками."""
    if len(text) < _MIN_NER_TEXT_LEN:
        return

    # Быстрая проверка наличия кириллицы на первых 500 символах как сэмпл
    sample = text[:500]
    cyr_count = sum(1 for c in sample if "\u0400" <= c <= "\u04FF")
    if cyr_count < len(sample) * _MIN_CYR_RATIO:
        return

    bundle = _bundle()
    if bundle is None:
        return

    Doc = bundle["Doc"]
    segmenter = bundle["segmenter"]
    morph_tagger = bundle["morph_tagger"]
    ner_tagger = bundle["ner_tagger"]

    offset = 0
    while offset < len(text):
        chunk = text[offset:offset + max_chars]
        try:
            doc = Doc(chunk)
            doc.segment(segmenter)
            doc.tag_morph(morph_tagger)
            doc.tag_ner(ner_tagger)
        except Exception:
            offset += max_chars
            continue

        for span in doc.spans:
            category: PIICategory | None = None
            if span.type == "PER":
                category = PIICategory.FIO
            elif span.type == "LOC":
                category = PIICategory.ADDRESS
            
            if category is None:
                continue

            value = span.text

            # --- ЗАЩИТА ОТ ЛОЖНЫХ СРАБАТЫВАНИЙ ---
            # 1. Если есть латиница — это не целевые ПДн граждан РФ (отсеивает английские ФИО/Адреса)
            if _LATIN_RE.search(value):
                continue
            
            # 2. Должна быть хотя бы одна русская гласная.
            # Отсеивает OCR-мусор и инициалы без фамилий вида "С. М.", "В. В.", "Д. Н. R."
            if not _RUS_VOWEL_RE.search(value):
                continue
            
            # 3. Чистый буквенный текст должен быть длиннее 2 символов
            alpha_only = re.sub(r"\W", "", value)
            if len(alpha_only) < 3:
                continue
            # -------------------------------------

            yield RawMatch(
                category=category,
                value=value,
                start=offset + span.start,
                end=offset + span.stop,
                confidence=0.85,
            )
        offset += max_chars