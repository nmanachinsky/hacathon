"""Настройка structlog для конвейера."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Сконфигурировать structlog один раз на процесс."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=log_level)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
