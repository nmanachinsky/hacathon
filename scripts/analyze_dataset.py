"""Скрипт детального анализа структуры датасета.

Запуск:
    uv run python scripts/analyze_dataset.py --input ./data/share --output docs/DATASET_REPORT.md
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def analyze(root: Path) -> dict:
    by_ext: Counter[str] = Counter()
    sizes_by_ext: dict[str, int] = {}
    files_by_dir: Counter[str] = Counter()
    rows_estimates: dict[str, int] = {}
    samples_per_ext: dict[str, list[str]] = {}
    biggest: list[tuple[int, Path]] = []
    total_size = 0
    total_files = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            sz = path.stat().st_size
        except OSError:
            sz = 0
        ext = path.suffix.lower() or "(без расш.)"
        by_ext[ext] += 1
        sizes_by_ext[ext] = sizes_by_ext.get(ext, 0) + sz
        total_size += sz
        total_files += 1
        biggest.append((sz, path))

        rel_top = path.relative_to(root).parts[0] if path.relative_to(root).parts else ""
        files_by_dir[rel_top] += 1

        samples_per_ext.setdefault(ext, [])
        if len(samples_per_ext[ext]) < 3:
            samples_per_ext[ext].append(str(path.relative_to(root)))

        # Грубая оценка строк для CSV/JSONL
        if ext in {".csv", ".tsv", ".jsonl"} and sz < 50 * 1024 * 1024:
            try:
                with path.open("rb") as f:
                    rows = sum(1 for _ in f)
                rows_estimates[str(path.relative_to(root))] = rows
            except OSError:
                pass

    biggest.sort(reverse=True)
    return {
        "root": str(root),
        "total_files": total_files,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "by_extension": dict(by_ext),
        "size_by_extension_mb": {k: round(v / 1024 / 1024, 2) for k, v in sizes_by_ext.items()},
        "files_by_top_dir": dict(files_by_dir),
        "samples_per_ext": samples_per_ext,
        "rows_in_csv_jsonl": rows_estimates,
        "biggest_files": [
            {"size_mb": round(sz / 1024 / 1024, 2), "path": str(p.relative_to(root))}
            for sz, p in biggest[:30]
        ],
    }


def render_markdown(stats: dict) -> str:
    lines = [
        "# Анализ датасета",
        "",
        f"**Корневая директория:** `{stats['root']}`",
        "",
        f"- Всего файлов: **{stats['total_files']}**",
        f"- Общий размер: **{stats['total_size_mb']} МБ**",
        "",
        "## Распределение по расширениям",
        "",
        "| Расширение | Файлов | Размер, МБ | Примеры |",
        "|------------|--------|------------|---------|",
    ]
    for ext, n in sorted(stats["by_extension"].items(), key=lambda x: -x[1]):
        size_mb = stats["size_by_extension_mb"].get(ext, 0)
        samples = ", ".join(f"`{s}`" for s in stats["samples_per_ext"].get(ext, [])[:2])
        lines.append(f"| `{ext}` | {n} | {size_mb} | {samples} |")

    lines.extend(["", "## Файлов по корневым каталогам", ""])
    lines.append("| Каталог | Файлов |")
    lines.append("|---------|--------|")
    for d, n in sorted(stats["files_by_top_dir"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{d}/` | {n} |")

    if stats["rows_in_csv_jsonl"]:
        lines.extend(["", "## Структурированные файлы — оценка количества строк", ""])
        lines.append("| Файл | Строк |")
        lines.append("|------|-------|")
        for p, rows in sorted(stats["rows_in_csv_jsonl"].items(), key=lambda x: -x[1])[:25]:
            lines.append(f"| `{p}` | {rows} |")

    lines.extend(["", "## Топ-30 крупнейших файлов", ""])
    for entry in stats["biggest_files"]:
        lines.append(f"- {entry['size_mb']} МБ — `{entry['path']}`")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Анализ датасета")
    parser.add_argument("--input", "-i", required=True, type=Path)
    parser.add_argument("--output", "-o", default=Path("docs/DATASET_REPORT.md"), type=Path)
    parser.add_argument("--json", default=None, type=Path, help="Доп. JSON-выгрузка")
    args = parser.parse_args()

    stats = analyze(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(stats), encoding="utf-8")
    print(f"Markdown отчёт: {args.output}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON отчёт: {args.json}")


if __name__ == "__main__":
    main()
