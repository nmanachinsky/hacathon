"""Загрузка и валидация конфигурации."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class ScanCfg(BaseModel):
    workers: int = 8
    ocr_workers: int = 2
    max_file_size_mb: int = 200
    max_pdf_pages: int = 500
    enable_dedup: bool = True
    checkpoint_path: str = "reports/.checkpoint.jsonl"


class OCRPreprocess(BaseModel):
    deskew: bool = True
    binarize: bool = True
    upscale: float = 2.0


class OCRCfg(BaseModel):
    mode: Literal["auto", "always", "off"] = "auto"
    backend: Literal["tesseract", "paddle"] = "tesseract"
    languages: list[str] = Field(default_factory=lambda: ["rus", "eng"])
    min_side_px: int = 200
    preprocess: OCRPreprocess = Field(default_factory=OCRPreprocess)


class DetectCfg(BaseModel):
    min_confidence: float = 0.6
    context_window: int = 60
    use_ner: bool = True
    ner_max_chars: int = 50000
    max_chunks_per_file: int = 10000


class ClassificationCfg(BaseModel):
    state_id_large_count: int = 10
    state_id_large_ratio: float = 0.01
    regular_pii_large_count: int = 50
    regular_pii_large_ratio: float = 0.10


class ReportingCfg(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["csv", "json", "md", "html"])
    masking: Literal["full", "partial", "hash_only"] = "partial"
    store_value_hash: bool = True


class LoggingCfg(BaseModel):
    level: str = "INFO"
    json_output: bool = Field(default=False, alias="json")

    model_config = {"populate_by_name": True}


class AppConfig(BaseModel):
    scan: ScanCfg = Field(default_factory=ScanCfg)
    ocr: OCRCfg = Field(default_factory=OCRCfg)
    detect: DetectCfg = Field(default_factory=DetectCfg)
    classification: ClassificationCfg = Field(default_factory=ClassificationCfg)
    reporting: ReportingCfg = Field(default_factory=ReportingCfg)
    logging: LoggingCfg = Field(default_factory=LoggingCfg)


def load_config(path: Path | None = None) -> AppConfig:
    """Загрузить конфиг из YAML; при отсутствии — вернуть дефолты."""
    candidate = path or DEFAULT_CONFIG_PATH
    if not candidate.exists():
        return AppConfig()
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AppConfig.model_validate(data)
