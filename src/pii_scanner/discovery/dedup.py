"""Дедупликация файлов по содержимому (xxhash)."""

from __future__ import annotations

from pathlib import Path

import xxhash

_CHUNK = 1024 * 1024  # 1 MiB


def hash_file(path: Path, chunk_size: int = _CHUNK) -> str:
    """Быстрый xxh3-128 хэш содержимого файла. Возвращает hex-строку."""
    h = xxhash.xxh3_128()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class HashRegistry:
    """Регистр хэшей: позволяет узнать, видели ли уже такой контент."""

    def __init__(self) -> None:
        self._seen: dict[str, Path] = {}
        self._duplicates: dict[Path, Path] = {}

    def register(self, path: Path, content_hash: str) -> bool:
        """Зарегистрировать файл; вернуть True, если файл новый."""
        if content_hash in self._seen:
            self._duplicates[path] = self._seen[content_hash]
            return False
        self._seen[content_hash] = path
        return True

    def duplicate_of(self, path: Path) -> Path | None:
        return self._duplicates.get(path)

    @property
    def total_unique(self) -> int:
        return len(self._seen)

    @property
    def total_duplicates(self) -> int:
        return len(self._duplicates)
