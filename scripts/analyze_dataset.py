"""Глубокий анализ файлового датасета перед сканированием PII.

Готовит детальный отчёт о структуре, форматах, дубликатах, схемах
структурированных файлов и подозрительных именах. Помогает оператору
оценить нагрузку, выбрать OCR-режим и подсветить заведомо-ПДн файлы.

Запуск:
    uv run python scripts/analyze_dataset.py --input ./data/share \
        --output docs/DATASET_REPORT.md \
        --json docs/DATASET_REPORT.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Константы / категоризация форматов
# ---------------------------------------------------------------------------

FORMAT_GROUPS: dict[str, set[str]] = {
    "Документы": {".pdf", ".doc", ".docx", ".rtf", ".odt"},
    "Таблицы": {".xls", ".xlsx", ".ods", ".csv", ".tsv"},
    "Структурированные": {".json", ".jsonl", ".ndjson", ".parquet", ".xml", ".yaml", ".yml"},
    "Веб": {".html", ".htm", ".mhtml"},
    "Изображения": {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".bmp", ".webp"},
    "Видео": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".webm"},
    "Аудио": {".mp3", ".wav", ".flac", ".ogg", ".m4a"},
    "Архивы": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "Текстовые": {".txt", ".md", ".log"},
    "Код": {".py", ".js", ".ts", ".sql", ".sh"},
}

# Время на 1 МБ для эстимейта (в секундах, с одного worker'a)
PROCESSING_RATE_SEC_PER_MB: dict[str, float] = {
    "Документы": 0.40,
    "Таблицы": 0.30,
    "Структурированные": 0.15,
    "Веб": 0.05,
    "Изображения": 1.50,  # OCR — самое медленное
    "Видео": 4.00,         # ffmpeg + OCR ключевых кадров
    "Текстовые": 0.02,
    "Код": 0.02,
    "Прочее": 0.10,
}

# Подозрительные паттерны в именах файлов (вероятные ПДн).
# Каждое правило: (regex, ярлык категории, приоритет 1..3)
PII_NAME_RULES: list[tuple[re.Pattern[str], str, int]] = [
    (re.compile(r"паспорт|passport|pasport", re.I), "passport", 3),
    (re.compile(r"снилс|snils", re.I), "snils", 3),
    (re.compile(r"\binn\b|инн[_-]?\d?", re.I), "inn", 3),
    (re.compile(r"огрн|ogrn", re.I), "ogrn", 3),
    (re.compile(r"водит|driver[_-]?lic|вод[_-]?удост|prava|права\b", re.I), "driver_license", 3),
    (re.compile(r"справк[аи]|certificate|сертификат", re.I), "certificate", 1),
    (re.compile(r"согласие|consent|agreement|обработк[ау][_ ]п[дн]н", re.I), "pd_consent", 3),
    (re.compile(r"договор|contract|dogovor|соглашен", re.I), "contract", 2),
    (re.compile(r"анкет|questionnaire|form_app", re.I), "form", 2),
    (re.compile(r"резюме|resume|\bcv[_ -]", re.I), "resume", 2),
    (re.compile(r"клиент|client|customer|customers", re.I), "clients", 2),
    (re.compile(r"сотрудник|employee|staff|personnel|hr_", re.I), "employees", 2),
    (re.compile(r"зарплат|salary|payroll|оклад", re.I), "salary", 3),
    (re.compile(r"physical|physic|individual|fiz_lic|физ[_-]?лиц", re.I), "individuals", 3),
    (re.compile(r"диагноз|diagnos|медицин|medical|health", re.I), "health", 3),
    (re.compile(r"банк|bank|счет|account|карт[аы]|card", re.I), "payment", 2),
    (re.compile(r"\bca\d+_\d+", re.I), "scan_archive", 2),  # CA01_01.tif — типичная схема сканов
]

# Имена/паттерны колонок CSV/JSON/Parquet → категория ПДн (быстрая эвристика).
PII_COLUMN_RULES: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"^(e[._-]?mail|mail|почта|email)$", re.I),
    "phone": re.compile(r"^(phone|tel|телефон|tel_no|mobile|mob|sotov)", re.I),
    "fio": re.compile(r"^(fio|fullname|full_name|фио|имя|name|surname|фамил|patronymic|отчеств)", re.I),
    "passport": re.compile(r"^(passport|паспорт|pasport|series|серия|number|номер_документ)", re.I),
    "snils": re.compile(r"^(snils|снилс|pension)", re.I),
    "inn": re.compile(r"^(inn|инн|tax)", re.I),
    "ogrn": re.compile(r"^(ogrn|огрн)", re.I),
    "birth": re.compile(r"(birth|др|d[._-]?o[._-]?b|dob|рожден|birthday|birth_date)", re.I),
    "address": re.compile(r"^(address|адрес|street|улиц|город|city|country|страна|регион|region)", re.I),
    "card": re.compile(r"(card|карт|pan|card_no|card_number)", re.I),
    "account": re.compile(r"(account|счет|account_no|sch[_-]?ras)", re.I),
    "bik": re.compile(r"^(bik|бик)$", re.I),
    "salary": re.compile(r"^(salary|зарплат|оклад|payroll|earnings)", re.I),
    "gender": re.compile(r"^(gender|sex|пол)$", re.I),
    "diagnosis": re.compile(r"(diagnos|диагноз)", re.I),
    "religion": re.compile(r"(религ|religion|confess)", re.I),
}

# Бакеты размеров для гистограммы
SIZE_BUCKETS_BYTES: list[tuple[str, int]] = [
    ("0", 0),
    ("≤1 KB", 1024),
    ("≤10 KB", 10 * 1024),
    ("≤100 KB", 100 * 1024),
    ("≤1 MB", 1024**2),
    ("≤10 MB", 10 * 1024**2),
    ("≤100 MB", 100 * 1024**2),
    ("≤1 GB", 1024**3),
    (">1 GB", float("inf")),  # type: ignore[list-item]
]

IGNORED_NAMES = {".DS_Store", "Thumbs.db", "__pycache__", ".idea", ".vscode"}


# ---------------------------------------------------------------------------
# Сбор файлов
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FileInfo:
    path: Path
    rel: Path
    size: int
    mtime: float
    ext: str
    group: str
    depth: int


def _format_group(ext: str) -> str:
    for group, exts in FORMAT_GROUPS.items():
        if ext in exts:
            return group
    return "Прочее"


def collect_files(root: Path) -> list[FileInfo]:
    files: list[FileInfo] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in IGNORED_NAMES:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        rel = path.relative_to(root)
        ext = path.suffix.lower() or "(без расш.)"
        files.append(
            FileInfo(
                path=path,
                rel=rel,
                size=stat.st_size,
                mtime=stat.st_mtime,
                ext=ext,
                group=_format_group(ext),
                depth=len(rel.parts) - 1,
            )
        )
    return files


# ---------------------------------------------------------------------------
# Аналитические блоки
# ---------------------------------------------------------------------------


def analyze_overview(files: list[FileInfo], root: Path) -> dict:
    sizes = [f.size for f in files]
    return {
        "root": str(root),
        "total_files": len(files),
        "total_size_mb": round(sum(sizes) / 1024**2, 2),
        "median_size_kb": round(statistics.median(sizes) / 1024, 2) if sizes else 0,
        "mean_size_kb": round(statistics.fmean(sizes) / 1024, 2) if sizes else 0,
        "p95_size_kb": round(_percentile(sizes, 0.95) / 1024, 2) if sizes else 0,
        "p99_size_mb": round(_percentile(sizes, 0.99) / 1024**2, 2) if sizes else 0,
        "max_size_mb": round(max(sizes, default=0) / 1024**2, 2),
        "empty_files": sum(1 for s in sizes if s == 0),
    }


def _percentile(values: list[int], q: float) -> float:
    if not values:
        return 0
    s = sorted(values)
    idx = min(len(s) - 1, int(len(s) * q))
    return s[idx]


def analyze_extensions(files: list[FileInfo]) -> list[dict]:
    by_ext: defaultdict[str, list[int]] = defaultdict(list)
    samples: defaultdict[str, list[str]] = defaultdict(list)
    groups: dict[str, str] = {}
    for f in files:
        by_ext[f.ext].append(f.size)
        groups[f.ext] = f.group
        if len(samples[f.ext]) < 3:
            samples[f.ext].append(str(f.rel))

    rows: list[dict] = []
    for ext, sizes in sorted(by_ext.items(), key=lambda kv: -len(kv[1])):
        rows.append({
            "ext": ext,
            "group": groups[ext],
            "count": len(sizes),
            "size_mb": round(sum(sizes) / 1024**2, 2),
            "median_kb": round(statistics.median(sizes) / 1024, 2) if sizes else 0,
            "max_mb": round(max(sizes) / 1024**2, 2),
            "samples": samples[ext],
        })
    return rows


def analyze_groups(files: list[FileInfo]) -> list[dict]:
    by_group: defaultdict[str, list[int]] = defaultdict(list)
    for f in files:
        by_group[f.group].append(f.size)
    rows = [
        {
            "group": g,
            "count": len(sizes),
            "size_mb": round(sum(sizes) / 1024**2, 2),
            "share_pct": round(100 * len(sizes) / max(1, len(files)), 1),
        }
        for g, sizes in by_group.items()
    ]
    rows.sort(key=lambda r: -r["count"])
    return rows


def analyze_size_histogram(files: list[FileInfo]) -> list[dict]:
    counter: Counter[str] = Counter()
    sums: defaultdict[str, int] = defaultdict(int)
    for f in files:
        for label, upper in SIZE_BUCKETS_BYTES:
            if f.size <= upper:
                counter[label] += 1
                sums[label] += f.size
                break
    return [
        {"bucket": label, "count": counter[label], "total_mb": round(sums[label] / 1024**2, 2)}
        for label, _ in SIZE_BUCKETS_BYTES
    ]


def analyze_age_histogram(files: list[FileInfo]) -> list[dict]:
    by_year: Counter[int] = Counter()
    for f in files:
        try:
            year = datetime.fromtimestamp(f.mtime).year
        except (OSError, ValueError, OverflowError):
            continue
        by_year[year] += 1
    return [{"year": y, "count": n} for y, n in sorted(by_year.items())]


def analyze_directory_tree(files: list[FileInfo]) -> dict:
    by_top: defaultdict[str, list[int]] = defaultdict(list)
    by_depth: Counter[int] = Counter()
    for f in files:
        top = f.rel.parts[0] if f.rel.parts else "(root)"
        by_top[top].append(f.size)
        by_depth[f.depth] += 1
    top_dirs = sorted(
        (
            {
                "path": d,
                "files": len(sizes),
                "size_mb": round(sum(sizes) / 1024**2, 2),
            }
            for d, sizes in by_top.items()
        ),
        key=lambda x: -x["files"],
    )
    return {
        "top_dirs": top_dirs,
        "depth_histogram": [{"depth": d, "count": by_depth[d]} for d in sorted(by_depth)],
        "max_depth": max(by_depth, default=0),
    }


def analyze_duplicates(files: list[FileInfo], max_size_mb: int = 50) -> dict:
    """Детект дубликатов через xxhash. Тяжёлые файлы пропускаются для скорости."""
    try:
        import xxhash
    except ImportError:
        return {"available": False}

    by_hash: defaultdict[str, list[FileInfo]] = defaultdict(list)
    skipped = 0
    for f in files:
        if f.size > max_size_mb * 1024**2:
            skipped += 1
            continue
        try:
            h = xxhash.xxh3_128()
            with f.path.open("rb") as fp:
                while chunk := fp.read(1024 * 1024):
                    h.update(chunk)
            by_hash[h.hexdigest()].append(f)
        except OSError:
            continue

    duplicate_groups = [g for g in by_hash.values() if len(g) > 1]
    duplicate_groups.sort(key=lambda g: -len(g))
    bytes_saved = sum(g[0].size * (len(g) - 1) for g in duplicate_groups)

    examples = [
        {
            "size_kb": round(g[0].size / 1024, 2),
            "copies": len(g),
            "paths": [str(f.rel) for f in g[:5]],
        }
        for g in duplicate_groups[:15]
    ]
    return {
        "available": True,
        "scanned": len(files) - skipped,
        "skipped_too_large": skipped,
        "unique_files": len(by_hash),
        "duplicate_groups": len(duplicate_groups),
        "total_duplicates": sum(len(g) - 1 for g in duplicate_groups),
        "bytes_saved_mb": round(bytes_saved / 1024**2, 2),
        "top_groups": examples,
    }


def analyze_suspicious_names(files: list[FileInfo]) -> dict:
    by_label: defaultdict[str, list[tuple[int, str]]] = defaultdict(list)
    flagged = 0
    for f in files:
        path_str = str(f.rel)
        matched = False
        for pattern, label, _prio in PII_NAME_RULES:
            if pattern.search(path_str):
                by_label[label].append((f.size, path_str))
                matched = True
        if matched:
            flagged += 1

    summary = sorted(
        (
            {
                "label": label,
                "count": len(items),
                "total_mb": round(sum(s for s, _ in items) / 1024**2, 2),
                "samples": [p for _, p in sorted(items, key=lambda x: -x[0])[:3]],
            }
            for label, items in by_label.items()
        ),
        key=lambda r: -r["count"],
    )
    return {"flagged_files": flagged, "by_label": summary}


def analyze_csv_schemas(files: list[FileInfo], limit: int = 25) -> list[dict]:
    """Прочитать только заголовки CSV — определить кандидатные PII-колонки."""
    csv_files = sorted(
        (f for f in files if f.ext in {".csv", ".tsv"}),
        key=lambda f: -f.size,
    )[:limit]
    rows: list[dict] = []
    for f in csv_files:
        try:
            with f.path.open("rb") as fp:
                head = fp.read(64 * 1024)
            text = head.decode("utf-8", errors="ignore")
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(text[:4096])
                delim = dialect.delimiter
            except csv.Error:
                delim = "\t" if f.ext == ".tsv" else ","
            reader = csv.reader(io.StringIO(text), delimiter=delim)
            header = next(reader, [])
            pii_hits = _match_pii_columns(header)
            rows.append({
                "path": str(f.rel),
                "size_kb": round(f.size / 1024, 2),
                "delimiter": repr(delim),
                "columns": header,
                "pii_columns": pii_hits,
            })
        except OSError:
            continue
    return rows


def analyze_json_schemas(files: list[FileInfo], limit: int = 15) -> list[dict]:
    json_files = sorted(
        (f for f in files if f.ext in {".json", ".jsonl", ".ndjson"}),
        key=lambda f: -f.size,
    )[:limit]
    rows: list[dict] = []
    for f in json_files:
        try:
            with f.path.open("rb") as fp:
                head = fp.read(64 * 1024).decode("utf-8", errors="ignore")
        except OSError:
            continue
        keys: list[str] = []
        try:
            if f.ext == ".json":
                obj = json.loads(head)
                if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                    keys = list(obj[0].keys())
                elif isinstance(obj, dict):
                    keys = list(obj.keys())
            else:
                first_line = head.split("\n", 1)[0]
                obj = json.loads(first_line)
                if isinstance(obj, dict):
                    keys = list(obj.keys())
        except (json.JSONDecodeError, ValueError):
            keys = []
        rows.append({
            "path": str(f.rel),
            "size_kb": round(f.size / 1024, 2),
            "top_keys": keys[:30],
            "pii_keys": _match_pii_columns(keys),
        })
    return rows


def analyze_parquet_schemas(files: list[FileInfo], limit: int = 10) -> list[dict]:
    parquet_files = [f for f in files if f.ext == ".parquet"][:limit]
    if not parquet_files:
        return []
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return []
    rows: list[dict] = []
    for f in parquet_files:
        try:
            schema = pq.read_schema(str(f.path))
            cols = [field.name for field in schema]
            rows.append({
                "path": str(f.rel),
                "size_kb": round(f.size / 1024, 2),
                "columns": cols,
                "pii_columns": _match_pii_columns(cols),
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"path": str(f.rel), "error": f"{type(exc).__name__}: {exc}"})
    return rows


def _match_pii_columns(columns: Iterable[str]) -> list[dict]:
    hits: list[dict] = []
    for col in columns:
        if not isinstance(col, str):
            continue
        for category, pattern in PII_COLUMN_RULES.items():
            if pattern.search(col):
                hits.append({"column": col, "category": category})
                break
    return hits


def estimate_workload(files: list[FileInfo], workers: int = 8) -> dict:
    by_group_seconds: defaultdict[str, float] = defaultdict(float)
    for f in files:
        rate = PROCESSING_RATE_SEC_PER_MB.get(f.group, PROCESSING_RATE_SEC_PER_MB["Прочее"])
        by_group_seconds[f.group] += (f.size / 1024**2) * rate

    total_sec_serial = sum(by_group_seconds.values())
    parallel_sec = total_sec_serial / max(1, workers)
    return {
        "workers_assumed": workers,
        "estimate_serial_minutes": round(total_sec_serial / 60, 1),
        "estimate_parallel_minutes": round(parallel_sec / 60, 1),
        "by_group_seconds": {g: round(s, 1) for g, s in sorted(by_group_seconds.items(), key=lambda x: -x[1])},
        "ocr_intensive_files": sum(1 for f in files if f.group in {"Изображения", "Видео"}),
    }


def biggest_and_oldest(files: list[FileInfo], n: int = 25) -> dict:
    biggest = sorted(files, key=lambda f: -f.size)[:n]
    oldest = sorted(files, key=lambda f: f.mtime)[:5]
    newest = sorted(files, key=lambda f: -f.mtime)[:5]
    return {
        "biggest": [{"size_mb": round(f.size / 1024**2, 2), "path": str(f.rel)} for f in biggest],
        "oldest": [{"date": _ts(f.mtime), "path": str(f.rel)} for f in oldest],
        "newest": [{"date": _ts(f.mtime), "path": str(f.rel)} for f in newest],
    }


def _ts(t: float) -> str:
    try:
        return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError, OverflowError):
        return "?"


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(report: dict) -> str:  # noqa: PLR0915 — отчётный код
    lines: list[str] = []
    ov = report["overview"]
    lines += [
        "# Анализ датасета",
        "",
        f"**Корневая директория:** `{ov['root']}`  ",
        f"**Сгенерировано:** {report['generated_at']}  ",
        f"**Время анализа:** {report['analysis_seconds']} сек",
        "",
        "## 1. Сводка",
        "",
        f"- Всего файлов: **{ov['total_files']}**",
        f"- Общий объём: **{ov['total_size_mb']} МБ**",
        f"- Размер медианного файла: **{ov['median_size_kb']} КБ** (среднее: {ov['mean_size_kb']} КБ)",
        f"- 95-й перцентиль: **{ov['p95_size_kb']} КБ**, 99-й: **{ov['p99_size_mb']} МБ**",
        f"- Самый большой файл: **{ov['max_size_mb']} МБ**",
        f"- Пустых файлов: **{ov['empty_files']}**",
        "",
    ]

    lines += ["## 2. Распределение по группам форматов", ""]
    lines += ["| Группа | Файлов | Размер, МБ | Доля |", "|--------|--------|------------|------|"]
    for g in report["groups"]:
        lines.append(f"| {g['group']} | {g['count']} | {g['size_mb']} | {g['share_pct']}% |")
    lines.append("")

    lines += ["## 3. Распределение по расширениям", ""]
    lines += [
        "| Расширение | Группа | Файлов | Объём, МБ | Медиана, КБ | Макс, МБ | Примеры |",
        "|------------|--------|--------|-----------|-------------|----------|---------|",
    ]
    for r in report["extensions"]:
        samples = ", ".join(f"`{s}`" for s in r["samples"][:2])
        lines.append(
            f"| `{r['ext']}` | {r['group']} | {r['count']} | {r['size_mb']} | "
            f"{r['median_kb']} | {r['max_mb']} | {samples} |"
        )
    lines.append("")

    lines += ["## 4. Гистограмма размеров", "", "| Бакет | Файлов | Объём, МБ |", "|-------|--------|-----------|"]
    for b in report["size_histogram"]:
        lines.append(f"| {b['bucket']} | {b['count']} | {b['total_mb']} |")
    lines.append("")

    if report["age_histogram"]:
        lines += ["## 5. Возраст (по mtime)", "", "| Год | Файлов |", "|-----|--------|"]
        for a in report["age_histogram"]:
            lines.append(f"| {a['year']} | {a['count']} |")
        lines.append("")

    tree = report["tree"]
    lines += [
        "## 6. Структура каталогов",
        "",
        f"Максимальная глубина вложенности: **{tree['max_depth']}**",
        "",
        "### Топ-каталогов (1-й уровень)",
        "",
        "| Каталог | Файлов | Объём, МБ |",
        "|---------|--------|-----------|",
    ]
    for d in tree["top_dirs"][:25]:
        lines.append(f"| `{d['path']}/` | {d['files']} | {d['size_mb']} |")
    lines.append("")

    lines += ["### Распределение по глубине вложенности", "", "| Глубина | Файлов |", "|---------|--------|"]
    for h in tree["depth_histogram"]:
        lines.append(f"| {h['depth']} | {h['count']} |")
    lines.append("")

    dups = report["duplicates"]
    lines += ["## 7. Дубликаты (xxhash xxh3-128)", ""]
    if not dups.get("available"):
        lines.append("_xxhash недоступен — пропустили дедуп._")
    else:
        lines += [
            f"- Просканировано хэшей: **{dups['scanned']}** (пропущено крупных: {dups['skipped_too_large']})",
            f"- Уникальных файлов: **{dups['unique_files']}**",
            f"- Групп дубликатов: **{dups['duplicate_groups']}**",
            f"- Суммарно повторных копий: **{dups['total_duplicates']}**",
            f"- Экономия за счёт дедупа: **{dups['bytes_saved_mb']} МБ**",
            "",
            "### Топ-группы дубликатов",
            "",
        ]
        for g in dups["top_groups"]:
            lines.append(f"- {g['copies']} копий × {g['size_kb']} КБ — `{g['paths'][0]}`")
            for p in g["paths"][1:]:
                lines.append(f"  - `{p}`")
    lines.append("")

    susp = report["suspicious_names"]
    lines += [
        "## 8. Подозрительные имена файлов",
        "",
        f"Файлов с признаками ПДн в имени/пути: **{susp['flagged_files']}**",
        "",
        "| Метка | Файлов | Объём, МБ | Примеры |",
        "|-------|--------|-----------|---------|",
    ]
    for entry in susp["by_label"]:
        samples = ", ".join(f"`{s}`" for s in entry["samples"])
        lines.append(f"| **{entry['label']}** | {entry['count']} | {entry['total_mb']} | {samples} |")
    lines.append("")

    if report["csv_schemas"]:
        lines += ["## 9. Схемы CSV/TSV (топ по размеру)", ""]
        for s in report["csv_schemas"]:
            cols = ", ".join(f"`{c}`" for c in s["columns"][:20])
            pii = ", ".join(f"**{h['column']}** → _{h['category']}_" for h in s["pii_columns"])
            lines += [
                f"### `{s['path']}` — {s['size_kb']} КБ (delimiter={s['delimiter']})",
                f"- Колонки: {cols}",
                f"- PII-кандидаты: {pii or '_не найдено_'}",
                "",
            ]

    if report["json_schemas"]:
        lines += ["## 10. Схемы JSON / JSONL", ""]
        for s in report["json_schemas"]:
            keys = ", ".join(f"`{k}`" for k in s["top_keys"])
            pii = ", ".join(f"**{h['column']}** → _{h['category']}_" for h in s["pii_keys"])
            lines += [
                f"### `{s['path']}` — {s['size_kb']} КБ",
                f"- Ключи верхнего уровня: {keys or '_не разобраны_'}",
                f"- PII-кандидаты: {pii or '_не найдено_'}",
                "",
            ]

    if report["parquet_schemas"]:
        lines += ["## 11. Схемы Parquet", ""]
        for s in report["parquet_schemas"]:
            if "error" in s:
                lines.append(f"- `{s['path']}` — ошибка: {s['error']}")
                continue
            cols = ", ".join(f"`{c}`" for c in s["columns"][:30])
            pii = ", ".join(f"**{h['column']}** → _{h['category']}_" for h in s["pii_columns"])
            lines += [
                f"### `{s['path']}` — {s['size_kb']} КБ",
                f"- Колонки: {cols}",
                f"- PII-кандидаты: {pii or '_не найдено_'}",
                "",
            ]

    est = report["workload"]
    lines += [
        "## 12. Оценка времени сканирования",
        "",
        f"- Файлов с OCR-нагрузкой (изображения/видео): **{est['ocr_intensive_files']}**",
        f"- Оценка последовательно: **{est['estimate_serial_minutes']} мин**",
        f"- Оценка с {est['workers_assumed']} воркерами: **{est['estimate_parallel_minutes']} мин**",
        "",
        "### Распределение нагрузки по группам (сек)",
        "",
        "| Группа | Время, сек |",
        "|--------|------------|",
    ]
    for g, sec in est["by_group_seconds"].items():
        lines.append(f"| {g} | {sec} |")
    lines.append("")

    bo = report["biggest_and_oldest"]
    lines += ["## 13. Топ-25 крупнейших файлов", ""]
    for entry in bo["biggest"]:
        lines.append(f"- {entry['size_mb']} МБ — `{entry['path']}`")
    lines += ["", "## 14. Самые старые / новые файлы", "", "**Старые:**"]
    for o in bo["oldest"]:
        lines.append(f"- {o['date']} — `{o['path']}`")
    lines.append("\n**Новые:**")
    for n in bo["newest"]:
        lines.append(f"- {n['date']} — `{n['path']}`")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Глубокий анализ файлового датасета")
    parser.add_argument("--input", "-i", required=True, type=Path, help="Корневая директория")
    parser.add_argument("--output", "-o", default=Path("docs/DATASET_REPORT.md"), type=Path)
    parser.add_argument("--json", default=None, type=Path, help="Дополнительный JSON-выгрузка")
    parser.add_argument("--workers", default=8, type=int, help="Воркеров для эстимейта")
    parser.add_argument("--no-dedup", action="store_true", help="Пропустить дедуп через xxhash")
    parser.add_argument("--dedup-max-mb", default=50, type=int, help="Лимит размера для дедупа")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"Директория не найдена: {args.input}")

    started = time.perf_counter()
    print(f"Сбор файлов из {args.input}…", file=sys.stderr)
    files = collect_files(args.input)
    print(f"  → найдено {len(files)} файлов", file=sys.stderr)

    print("Аналитика…", file=sys.stderr)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overview": analyze_overview(files, args.input),
        "groups": analyze_groups(files),
        "extensions": analyze_extensions(files),
        "size_histogram": analyze_size_histogram(files),
        "age_histogram": analyze_age_histogram(files),
        "tree": analyze_directory_tree(files),
        "duplicates": (
            {"available": False, "skipped_by_user": True}
            if args.no_dedup
            else analyze_duplicates(files, max_size_mb=args.dedup_max_mb)
        ),
        "suspicious_names": analyze_suspicious_names(files),
        "csv_schemas": analyze_csv_schemas(files),
        "json_schemas": analyze_json_schemas(files),
        "parquet_schemas": analyze_parquet_schemas(files),
        "workload": estimate_workload(files, workers=args.workers),
        "biggest_and_oldest": biggest_and_oldest(files),
    }
    report["analysis_seconds"] = round(time.perf_counter() - started, 2)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(report), encoding="utf-8")
    print(f"Markdown отчёт: {args.output}", file=sys.stderr)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"JSON отчёт: {args.json}", file=sys.stderr)

    print(f"Готово за {report['analysis_seconds']} сек", file=sys.stderr)


if __name__ == "__main__":
    main()
