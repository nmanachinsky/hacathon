"""Рекурсивный обход файловой системы."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

# Файлы и папки, которые игнорируем по имени
IGNORED_NAMES: frozenset[str] = frozenset({
    ".DS_Store",
    "Thumbs.db",
    ".git",
    ".venv",
    "__pycache__",
    "lost+found",
})

# Расширения, которые точно бесполезны
IGNORED_EXTENSIONS: frozenset[str] = frozenset({
    ".pyc", ".pyo", ".class",
    ".o", ".a", ".so", ".dll", ".dylib",
    ".exe", ".bin",
    ".lock", ".tmp", ".swp", ".bak",
})


def walk_files(root: Path, follow_symlinks: bool = False) -> Iterator[Path]:
    """Итеративный обход файлов под root в стабильном порядке."""
    root = root.resolve()
    if not root.exists():
        raise FileNotFoundError(root)

    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except (PermissionError, OSError):
            continue

        for entry in entries:
            name = entry.name
            if name in IGNORED_NAMES:
                continue
            try:
                is_symlink = entry.is_symlink()
                if is_symlink and not follow_symlinks:
                    continue
                if entry.is_dir():
                    stack.append(entry)
                elif entry.is_file():
                    if entry.suffix.lower() in IGNORED_EXTENSIONS:
                        continue
                    yield entry
            except (PermissionError, OSError):
                continue
