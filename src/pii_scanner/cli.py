"""Командная строка PII-сканера."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from .config import load_config
from .pipeline import run_scan
from .reporting.writers import build_summary, write_csv, write_html, write_json, write_markdown, write_result_csv
from .utils.logging import configure_logging

app = typer.Typer(help="Автоматическое обнаружение персональных данных (152-ФЗ)")
console = Console()


@app.command()
def scan(
    input_dir: Annotated[Path, typer.Option("--input", "-i", help="Корневая директория для сканирования", exists=True, file_okay=False, dir_okay=True)],
    output_dir: Annotated[Path, typer.Option("--output", "-o", help="Директория для отчётов")] = Path("reports"),
    config_path: Annotated[Path | None, typer.Option("--config", "-c", help="Путь к YAML конфигу")] = None,
    workers: Annotated[int | None, typer.Option("--workers", "-w", help="Число воркеров")] = None,
    formats: Annotated[str, typer.Option("--formats", help="Список форматов отчёта через запятую: csv,json,md,html")] = "csv,json,md,html",
    ocr: Annotated[str | None, typer.Option("--ocr", help="Режим OCR: auto|always|off")] = None,
    use_ner: Annotated[bool, typer.Option("--ner/--no-ner", help="Включить Natasha NER")] = True,
    log_level: Annotated[str, typer.Option("--log-level", help="DEBUG|INFO|WARNING|ERROR")] = "INFO",
) -> None:
    """Сканировать директорию и сформировать отчёты."""
    cfg = load_config(config_path)
    if workers is not None:
        cfg.scan.workers = workers
    if ocr is not None:
        cfg.ocr.mode = ocr  # type: ignore[assignment]
    cfg.detect.use_ner = use_ner
    cfg.logging.level = log_level

    configure_logging(level=cfg.logging.level, json_output=cfg.logging.json_output)

    output_dir.mkdir(parents=True, exist_ok=True)
    console.rule(f"[bold]Сканирование[/bold] {input_dir}")
    console.print(f"workers={cfg.scan.workers}  ocr={cfg.ocr.mode}  ner={cfg.detect.use_ner}")

    started = time.perf_counter()
    reports: list[dict] = []
    files_pre = sum(1 for _ in input_dir.rglob("*") if _.is_file())

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[current]}"),
        console=console,
        transient=False,
    ) as progress:
        task_id = progress.add_task("Обработка файлов", total=files_pre, current="")

        def cb(done: int, total: int, res: dict) -> None:
            try:
                rel = Path(res.get("path", "")).name
            except Exception:  # noqa: BLE001
                rel = ""
            if len(rel) > 60:
                rel = "…" + rel[-59:]
            progress.update(task_id, completed=done, total=total, current=rel)

        for res in run_scan(input_dir, cfg, progress_cb=cb):
            reports.append(res)

    elapsed = time.perf_counter() - started
    summary = build_summary(reports, elapsed=elapsed)

    selected = {f.strip().lower() for f in formats.split(",") if f.strip()}
    if "csv" in selected:
        write_csv(reports, output_dir / "report.csv")
    if "json" in selected:
        write_json(reports, summary, output_dir / "report.json")
    if "md" in selected:
        write_markdown(reports, summary, output_dir / "report.md")
    if "html" in selected:
        write_html(reports, summary, output_dir / "report.html")
    # Всегда генерируем result.csv для хакатонной системы проверки
    write_result_csv(reports, output_dir / "result.csv")

    console.rule("[bold green]Готово[/bold green]")
    _print_summary(summary, output_dir)


def _print_summary(summary: dict, output_dir: Path) -> None:
    table = Table(title="Сводка")
    table.add_column("Метрика", style="cyan")
    table.add_column("Значение", justify="right")
    table.add_row("Всего файлов", str(summary["total_files"]))
    table.add_row("С обнаруженными ПДн", str(summary["files_with_pii"]))
    table.add_row("Ошибок обработки", str(summary["errors"]))
    table.add_row("Время, сек", f"{summary['elapsed_seconds']:.1f}")
    console.print(table)

    lvl_table = Table(title="Распределение по УЗ")
    lvl_table.add_column("УЗ", style="magenta")
    lvl_table.add_column("Файлов", justify="right")
    for lvl, c in summary["protection_level_counts"].items():
        lvl_table.add_row(lvl, str(c))
    console.print(lvl_table)

    cat_table = Table(title="Топ-10 категорий ПДн")
    cat_table.add_column("Категория", style="yellow")
    cat_table.add_column("Найдено", justify="right")
    sorted_cats = sorted(summary["category_counts"].items(), key=lambda x: -x[1])[:10]
    for cat, c in sorted_cats:
        cat_table.add_row(cat, str(c))
    console.print(cat_table)

    console.print(f"\n[bold]Артефакты:[/bold] {output_dir.resolve()}")


@app.command()
def analyze(
    input_dir: Annotated[Path, typer.Option("--input", "-i", exists=True, file_okay=False, dir_okay=True)],
    output: Annotated[Path, typer.Option("--output", "-o", help="Куда писать отчёт")] = Path("docs/DATASET_REPORT.md"),
) -> None:
    """Предварительный анализ датасета (распределение по типам/размерам)."""
    from collections import Counter

    output.parent.mkdir(parents=True, exist_ok=True)
    by_ext: Counter[str] = Counter()
    sizes: dict[str, int] = {}
    total_size = 0
    total_files = 0
    biggest: list[tuple[int, Path]] = []

    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        ext = path.suffix.lower() or "(без расш.)"
        by_ext[ext] += 1
        try:
            sz = path.stat().st_size
        except OSError:
            sz = 0
        sizes[ext] = sizes.get(ext, 0) + sz
        total_size += sz
        total_files += 1
        biggest.append((sz, path))

    biggest.sort(reverse=True)
    biggest = biggest[:20]

    lines = [
        "# Анализ датасета",
        "",
        f"- Всего файлов: **{total_files}**",
        f"- Общий размер: **{total_size / 1024 / 1024:.1f} МБ**",
        "",
        "## Распределение по расширениям",
        "",
        "| Расширение | Файлов | Размер, МБ |",
        "|------------|--------|------------|",
    ]
    for ext, n in sorted(by_ext.items(), key=lambda x: -x[1]):
        lines.append(f"| `{ext}` | {n} | {sizes[ext] / 1024 / 1024:.2f} |")

    lines.extend(["", "## Топ-20 самых больших файлов", ""])
    for sz, p in biggest:
        lines.append(f"- {sz / 1024 / 1024:.2f} МБ — `{p}`")

    output.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]Отчёт записан:[/green] {output}")


@app.command()
def report(
    from_json: Annotated[Path, typer.Option("--from", help="Путь к report.json")],
    output_dir: Annotated[Path, typer.Option("--output", "-o")] = Path("reports"),
    formats: Annotated[str, typer.Option("--formats")] = "csv,md,html",
) -> None:
    """Перегенерировать отчёты из существующего JSON (без повторного сканирования)."""
    payload = json.loads(from_json.read_text(encoding="utf-8"))
    reports = payload["files"]
    summary = payload["summary"]
    selected = {f.strip().lower() for f in formats.split(",") if f.strip()}
    if "csv" in selected:
        write_csv(reports, output_dir / "report.csv")
    if "md" in selected:
        write_markdown(reports, summary, output_dir / "report.md")
    if "html" in selected:
        write_html(reports, summary, output_dir / "report.html")
    write_result_csv(reports, output_dir / "result.csv")
    console.print(f"[green]Готово:[/green] {output_dir}")


if __name__ == "__main__":
    app()
