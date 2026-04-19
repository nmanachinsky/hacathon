"""NER на базе Natasha — для уверенной детекции ФИО, локаций (адресов) и дат."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..types import PIICategory
from .base import RawMatch

# Ленивая инициализация — модели Natasha занимают ~150 МБ ОЗУ
_NER_BUNDLE: dict[str, Any] | None = None


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


def detect_ner(text: str, max_chars: int = 50_000) -> Iterable[RawMatch]:
    """Извлечь сущности через Natasha. На больших текстах — нарезаем чанками."""
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
            yield RawMatch(
                category=category,
                value=span.text,
                start=offset + span.start,
                end=offset + span.stop,
                confidence=0.85,
            )
        offset += max_chars
