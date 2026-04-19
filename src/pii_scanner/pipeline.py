"""Главный конвейер: enumerate → extract → detect → classify → report.

Реализован двухуровневый параллелизм:
- основной пул для лёгких форматов (PDF, HTML, текстовые),
- отдельный пул для OCR (изображения и PDF-сканы) — ограниченное число воркеров.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

from .classification.uz_classifier import classify
from .config import AppConfig
from .detectors.registry import detect_all
from .discovery.dedup import HashRegistry, hash_file
from .discovery.router import guess_kind, guess_mime
from .discovery.walker import walk_files
from .extractors.base import ExtractorError
from .extractors.dispatch import extract_text
from .reporting.masking import mask_value, sha256_hex
from .types import (
    Finding,
    FileMeta,
    FileReport,
    PIICategory,
    ProtectionLevel,
    TextChunk,
)

# Файловые форматы, требующие OCR: обрабатываем отдельным пулом с ограниченным параллелизмом
_OCR_KINDS = frozenset({"image", "video"})
from .utils.logging import get_logger

log = get_logger(__name__)

# ---- Извлечение rows_processed из локаторов ----
_ROWS_RE = re.compile(r"rows=(\d+)")


def _rows_from_locator(locator: str) -> int:
    m = _ROWS_RE.search(locator)
    return int(m.group(1)) if m else 0


# ---- Worker function ----

def _silence_noisy_loggers() -> None:
    """Глушим болтливые библиотеки — pypdf/pdfminer/PIL засоряют stderr на каждом битом PDF."""
    import logging as _logging

    for name in (
        "pypdf",
        "pypdf._reader",
        "pypdf.generic",
        "pdfminer",
        "pdfminer.pdfparser",
        "pdfminer.pdfdocument",
        "pdfminer.pdfinterp",
        "pdfminer.cmapdb",
        "pdfplumber",
        "PIL",
        "trafilatura",
    ):
        _logging.getLogger(name).setLevel(_logging.ERROR)


def process_file(
    path_str: str,
    cfg_dict: dict,
) -> dict:
    """Запускается в подпроцессе. Возвращает сериализуемый dict с результатом."""
    from .config import AppConfig as _AppConfig

    _silence_noisy_loggers()
    cfg = _AppConfig.model_validate(cfg_dict)
    path = Path(path_str)
    started = time.perf_counter()

    try:
        _stat = path.stat()
        size = _stat.st_size
        mtime = _stat.st_mtime
    except OSError as exc:
        return _failed_report(path, str(exc), 0, time.perf_counter() - started)

    kind = guess_kind(path)
    if kind is None:
        return _failed_report(path, "unsupported_format", size, time.perf_counter() - started)

    raw_findings: list[tuple[PIICategory, str, float]] = []
    text_length = 0
    rows_processed = 0
    error: str | None = None

    try:
        chunks: Iterator[TextChunk] = extract_text(
            path,
            ocr_cfg=cfg.ocr,
            max_pdf_pages=cfg.scan.max_pdf_pages,
        )
        chunks_seen = 0
        for chunk in chunks:
            chunks_seen += 1
            if chunks_seen > cfg.detect.max_chunks_per_file:
                break
            text_length += len(chunk.text)
            rows_processed += _rows_from_locator(chunk.locator)
            # Структурированные данные (CSV/Parquet) содержат [[PII_DIRECT:]] маркеры —
            # NER на них бесполезен и только замедляет обработку
            has_direct_markers = "[[PII_DIRECT:" in chunk.text
            for raw in detect_all(
                chunk.text,
                use_ner=cfg.detect.use_ner and not has_direct_markers,
                ner_max_chars=cfg.detect.ner_max_chars,
                context_radius=cfg.detect.context_window,
                min_confidence=cfg.detect.min_confidence,
            ):
                raw_findings.append((raw.category, raw.value, raw.confidence))
    except ExtractorError as exc:
        error = f"extract_error: {exc}"
    except Exception as exc:  # noqa: BLE001
        error = f"unhandled: {type(exc).__name__}: {exc}"

    # Дедуп находок внутри файла по (категория, hash значения)
    seen_pairs: set[tuple[PIICategory, str]] = set()
    findings_serialized: list[dict] = []
    counts: Counter[PIICategory] = Counter()
    for category, value, conf in raw_findings:
        value_str = str(value).strip()
        if not value_str:
            continue
        h = sha256_hex(value_str)
        key = (category, h)
        if key in seen_pairs:
            counts[category] += 1
            continue
        seen_pairs.add(key)
        counts[category] += 1
        findings_serialized.append({
            "category": category.value,
            "value_masked": mask_value(value_str, category, cfg.reporting.masking),
            "value_hash": h if cfg.reporting.store_value_hash else "",
            "confidence": round(conf, 3),
        })

    level = classify(dict(counts), rows_processed=rows_processed, cfg=cfg.classification)

    return {
        "path": str(path),
        "size": size,
        "mtime": mtime,
        "extension": path.suffix.lower(),
        "mime": guess_mime(path),
        "kind": kind,
        "findings": findings_serialized,
        "category_counts": {k.value: v for k, v in counts.items()},
        "protection_level": level.value,
        "error": error,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "text_length": text_length,
        "rows_processed": rows_processed,
    }


def _failed_report(path: Path, error: str, size: int, elapsed: float) -> dict:
    return {
        "path": str(path),
        "size": size,
        "extension": path.suffix.lower(),
        "mime": guess_mime(path),
        "kind": None,
        "findings": [],
        "category_counts": {},
        "protection_level": ProtectionLevel.NONE.value,
        "error": error,
        "elapsed_seconds": round(elapsed, 3),
        "text_length": 0,
        "rows_processed": 0,
    }


# ---- Orchestration ----

def _dedup_parallel(files: list[Path], workers: int) -> list[Path]:
    """Параллельное хэширование файлов для дедупликации (I/O-bound → ThreadPool)."""
    registry = HashRegistry()
    deduped: list[Path] = []

    def _hash_one(path: Path) -> tuple[Path, str | None]:
        try:
            return path, hash_file(path)
        except OSError as exc:
            log.warning("hash_failed", path=str(path), err=str(exc))
            return path, None

    # ThreadPool эффективен для I/O-bound хэширования файлов
    thread_workers = min(workers * 2, 32, len(files))
    with ThreadPoolExecutor(max_workers=max(1, thread_workers)) as pool:
        for path, h in pool.map(_hash_one, files):
            if h is None:
                deduped.append(path)  # ошибка хэширования — обрабатываем всё равно
            elif registry.register(path, h):
                deduped.append(path)

    log.info("dedup_done", unique=registry.total_unique, duplicates=registry.total_duplicates)
    return deduped


def run_scan(
    input_dir: Path,
    cfg: AppConfig,
    *,
    progress_cb=None,
) -> Iterator[dict]:
    """Запустить сканирование и стримить результаты по мере готовности."""
    files = list(walk_files(input_dir))
    log.info("scan_start", total_files=len(files), workers=cfg.scan.workers)

    deduped = _dedup_parallel(files, cfg.scan.workers) if cfg.scan.enable_dedup else files

    cfg_dict = cfg.model_dump()
    workers = max(1, cfg.scan.workers)
    ocr_workers = max(1, cfg.scan.ocr_workers)
    total = len(deduped)
    completed = 0

    # Разделяем по тяжести: OCR-файлы идут в отдельный ограниченный пул,
    # чтобы Tesseract не насыщал все CPU-ядра одновременно
    light: list[Path] = []
    heavy: list[Path] = []
    for p in deduped:
        kind = guess_kind(p)
        (heavy if kind in _OCR_KINDS else light).append(p)

    # Лёгкие файлы — по размеру: маленькие сначала для быстрого первого результата
    try:
        light.sort(key=lambda p: p.stat().st_size)
    except OSError:
        pass

    def _yield_from_pool(executor: ProcessPoolExecutor, paths: list[Path]) -> Iterator[dict]:
        nonlocal completed
        futs = {executor.submit(process_file, str(p), cfg_dict): p for p in paths}
        for fut in as_completed(futs):
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001
                p = futs[fut]
                res = _failed_report(p, f"worker_crash: {exc}", 0, 0.0)
            completed += 1
            if progress_cb:
                progress_cb(completed, total, res)
            yield res

    if workers == 1:
        for path in light + heavy:
            res = process_file(str(path), cfg_dict)
            completed += 1
            if progress_cb:
                progress_cb(completed, total, res)
            yield res
        return

    # Лёгкие файлы (текст, PDF, HTML, CSV) — основной пул с полным числом воркеров
    with ProcessPoolExecutor(max_workers=workers) as ex:
        yield from _yield_from_pool(ex, light)

    # OCR-файлы (изображения, видео) — ограниченный пул: Tesseract очень CPU-тяжёл
    if heavy:
        with ProcessPoolExecutor(max_workers=ocr_workers) as ex:
            yield from _yield_from_pool(ex, heavy)
