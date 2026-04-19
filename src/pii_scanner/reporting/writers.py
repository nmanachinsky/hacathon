"""Запись отчётов в CSV / JSON / Markdown / HTML."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

from ..classification.uz_classifier import recommendations_for
from ..types import ProtectionLevel


# ---- CSV (формат строго по ТЗ) ----

CSV_COLUMNS = ["путь", "категории_ПДн", "количество_находок", "УЗ", "формат_файла", "рекомендации"]


def write_csv(reports: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CSV_COLUMNS)
        for r in reports:
            counts = r.get("category_counts", {})
            cats = "|".join(sorted(counts.keys())) if counts else ""
            total = sum(counts.values())
            level = r.get("protection_level", ProtectionLevel.NONE.value)
            try:
                recs = recommendations_for(ProtectionLevel(level))
            except ValueError:
                recs = ""
            writer.writerow([
                r.get("path", ""),
                cats,
                total,
                level,
                r.get("extension", "").lstrip("."),
                recs,
            ])


# ---- result.csv (формат хакатона: size,time,name) ----
#
# Метрика: (TP - 0.1*FP) / (TP + FN) — каждый FP стоит 0.1 TP.
# Стратегия: пускаем в result.csv ТОЛЬКО файлы с уверенными признаками ПДн.
# Слабые сигналы (одиночное ФИО от NER, единственный email/телефон) — отбрасываем.

# Категории, само наличие которых — сильный сигнал (валидаторы Luhn/SNILS/INN/BIK,
# спецкатегории, биометрия — все они уже жёстко отфильтрованы детекторами).
_HIGH_CONFIDENCE_CATEGORIES = frozenset({
    "passport_rf", "snils", "inn_personal", "driver_license", "mrz", 
    "bank_card", "bank_account", "bik", "cvv",
    "biometric", "health", "religion", "politics", "race", "other_sensitive"
})

# "Мягкие" категории (одиночное ФИО, город в тексте или ОГРН компании)
_WEAK_SINGLE_CATEGORIES = frozenset({"fio", "address", "birth_place", "ogrn", "inn_legal"})
# "Связующие" категории (превращают набор имен в реальную базу данных)
_MEDIUM_CATEGORIES = frozenset({"email", "phone", "birth_date"})


def _is_confident_pii(report: dict) -> bool:
    counts: dict[str, int] = report.get("category_counts") or {}
    if not counts:
        return False

    # 1. Если есть жесткий маркер (Паспорт, СНИЛС, Карта) -> это 100% утечка
    if any(cat in _HIGH_CONFIDENCE_CATEGORIES for cat in counts):
        return True

    # 2. ПРАВИЛО СВЯЗНОСТИ: Если нет жестких маркеров, проверяем связующие.
    has_medium = any(cat in _MEDIUM_CATEGORIES for cat in counts)
    
    # Если в файле только ФИО, Адреса и ОГРН, но НЕТ ни телефонов, ни email, ни дат рождения
    # -> это презентация, художественный текст или мануал. Отбрасываем.
    if not has_medium:
        return False

    # 3. Если связующие маркеры есть, требуем разнообразия (ФИО + email)
    # или массовости (список из 3+ email-ов).
    distinct_categories = len(counts)
    if distinct_categories >= 2:
        return True

    only_count = next(iter(counts.values()))
    return only_count >= 3


def _format_mtime(mtime_ts: float | None) -> str:
    if not mtime_ts:
        return ""
    dt = datetime.fromtimestamp(mtime_ts)
    return f"{dt.strftime('%b').lower()} {dt.day} {dt.strftime('%H:%M')}"


def write_result_csv(reports: list[dict], path: Path) -> None:
    """Записать result.csv только для файлов с уверенными ПДн.

    Формат строго: size,time,name. Только базовое имя файла (без пути).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["size", "time", "name"])
        for r in reports:
            if not _is_confident_pii(r):
                continue
            writer.writerow([
                r.get("size", 0),
                _format_mtime(r.get("mtime")),
                Path(r["path"]).name,
            ])


# ---- JSON (детальный) ----

def write_json(reports: list[dict], summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "files": reports}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---- Markdown (executive summary) ----

def write_markdown(reports: list[dict], summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Отчёт PII-сканера")
    lines.append("")
    lines.append(f"- Всего файлов проверено: **{summary['total_files']}**")
    lines.append(f"- С обнаруженными ПДн: **{summary['files_with_pii']}**")
    lines.append(f"- Ошибок обработки: **{summary['errors']}**")
    lines.append(f"- Общая длительность: **{summary['elapsed_seconds']:.1f} сек**")
    lines.append("")
    lines.append("## Распределение по уровням защиты")
    lines.append("")
    lines.append("| УЗ | Файлов |")
    lines.append("|----|--------|")
    for level, count in summary["protection_level_counts"].items():
        lines.append(f"| {level} | {count} |")
    lines.append("")
    lines.append("## Топ категорий ПДн")
    lines.append("")
    lines.append("| Категория | Находок |")
    lines.append("|-----------|---------|")
    for cat, c in sorted(summary["category_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"| {cat} | {c} |")
    lines.append("")
    lines.append("## Топ-20 файлов с наибольшим количеством ПДн")
    lines.append("")
    lines.append("| Файл | УЗ | Кол-во | Категории |")
    lines.append("|------|----|--------|-----------|")
    sorted_reports = sorted(
        reports,
        key=lambda r: sum(r.get("category_counts", {}).values()),
        reverse=True,
    )[:20]
    for r in sorted_reports:
        counts = r.get("category_counts", {})
        if not counts:
            continue
        total = sum(counts.values())
        cats = ", ".join(sorted(counts.keys()))
        lines.append(f"| `{r['path']}` | {r['protection_level']} | {total} | {cats} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---- HTML dashboard ----

_HTML_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>PII Scanner Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; color: #1a1a1a; background: #f6f8fa; }
  h1 { margin-top: 0; }
  .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 18px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; }
  .kpi { font-size: 32px; font-weight: 700; }
  .kpi-label { font-size: 13px; color: #586069; text-transform: uppercase; letter-spacing: .5px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #e1e4e8; vertical-align: top; }
  th { background: #f1f3f5; cursor: pointer; user-select: none; }
  tr:hover { background: #fafbfc; }
  .lvl { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
  .lvl-1 { background: #fde2e1; color: #7a0019; }
  .lvl-2 { background: #ffe6c7; color: #7a4400; }
  .lvl-3 { background: #fff3bf; color: #5a4500; }
  .lvl-4 { background: #d4edda; color: #155724; }
  .lvl-none { background: #e1e4e8; color: #586069; }
  input[type=search] { padding: 8px 12px; border: 1px solid #d0d7de; border-radius: 8px; width: 100%; max-width: 360px; }
  .chart-container { position: relative; height: 280px; }
  code { background: #f6f8fa; padding: 1px 5px; border-radius: 4px; font-size: 12px; }
  .err { color: #b00020; font-size: 11px; }
</style>
</head>
<body>
<h1>PII Scanner — отчёт</h1>
<p style="color:#586069;">Автоматический анализ персональных данных согласно 152-ФЗ. Найденные значения замаскированы.</p>

<div class="grid">
  <div class="card"><div class="kpi-label">Файлов проверено</div><div class="kpi">{{ summary.total_files }}</div></div>
  <div class="card"><div class="kpi-label">Содержат ПДн</div><div class="kpi">{{ summary.files_with_pii }}</div></div>
  <div class="card"><div class="kpi-label">Ошибок</div><div class="kpi">{{ summary.errors }}</div></div>
  <div class="card"><div class="kpi-label">Время обработки</div><div class="kpi">{{ "%.1f"|format(summary.elapsed_seconds) }}s</div></div>
</div>

<div class="grid">
  <div class="card"><h3>Уровни защиты</h3><div class="chart-container"><canvas id="lvlChart"></canvas></div></div>
  <div class="card"><h3>Категории ПДн (топ-12)</h3><div class="chart-container"><canvas id="catChart"></canvas></div></div>
  <div class="card"><h3>Распределение по форматам</h3><div class="chart-container"><canvas id="fmtChart"></canvas></div></div>
</div>

<div class="card">
  <h3>Файлы</h3>
  <input type="search" id="filter" placeholder="Фильтр по пути / категории / УЗ..." />
  <p style="color:#586069; font-size:12px;">Кликните по заголовкам для сортировки.</p>
  <div style="overflow:auto; max-height: 70vh;">
  <table id="files">
    <thead>
      <tr>
        <th data-key="path">Путь</th>
        <th data-key="ext">Формат</th>
        <th data-key="size">Размер</th>
        <th data-key="level">УЗ</th>
        <th data-key="total">Находок</th>
        <th>Категории (с количеством)</th>
        <th>Время</th>
      </tr>
    </thead>
    <tbody>
    {% for r in reports %}
      {% set total = r.category_counts.values()|sum %}
      <tr data-path="{{ r.path|lower }}" data-ext="{{ r.extension }}" data-size="{{ r.size }}" data-level="{{ r.protection_level }}" data-total="{{ total }}">
        <td><code>{{ r.path }}</code>{% if r.error %}<div class="err">{{ r.error }}</div>{% endif %}</td>
        <td>{{ r.extension }}</td>
        <td>{{ "%.1f"|format(r.size/1024) }} KB</td>
        <td><span class="lvl {{ level_class(r.protection_level) }}">{{ r.protection_level }}</span></td>
        <td>{{ total }}</td>
        <td>{{ format_categories(r.category_counts) }}</td>
        <td>{{ "%.2f"|format(r.elapsed_seconds) }}s</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>

<script>
const summary = {{ summary_json|safe }};

function makePie(id, labels, values, colors) {
  new Chart(document.getElementById(id), {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors }] },
    options: { plugins: { legend: { position: 'right' } }, maintainAspectRatio: false },
  });
}
function makeBar(id, labels, values) {
  new Chart(document.getElementById(id), {
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: '#5470c6' }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } }, maintainAspectRatio: false },
  });
}

const lvlColors = { 'УЗ-1': '#d62728', 'УЗ-2': '#ff7f0e', 'УЗ-3': '#fdcb6e', 'УЗ-4': '#2ca02c', 'Без ПДн': '#aaaaaa' };
const lvlLabels = Object.keys(summary.protection_level_counts);
makePie('lvlChart', lvlLabels, lvlLabels.map(l => summary.protection_level_counts[l]), lvlLabels.map(l => lvlColors[l] || '#888'));

const sortedCats = Object.entries(summary.category_counts).sort((a,b) => b[1] - a[1]).slice(0, 12);
makeBar('catChart', sortedCats.map(c => c[0]), sortedCats.map(c => c[1]));

const fmtEntries = Object.entries(summary.format_counts).sort((a,b) => b[1] - a[1]);
makePie('fmtChart', fmtEntries.map(e => e[0]), fmtEntries.map(e => e[1]),
  ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#3ba272','#fc8452','#9a60b4','#ea7ccc','#a0a7e6','#c4ccd3','#5b8ff9']);

// Filter
document.getElementById('filter').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('#files tbody tr').forEach(tr => {
    const txt = tr.textContent.toLowerCase();
    tr.style.display = txt.includes(q) ? '' : 'none';
  });
});

// Sort
document.querySelectorAll('#files thead th').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    if (!key) return;
    const rows = Array.from(document.querySelectorAll('#files tbody tr'));
    const dir = th.dataset.dir === 'asc' ? -1 : 1;
    th.dataset.dir = dir === 1 ? 'asc' : 'desc';
    rows.sort((a, b) => {
      const va = a.dataset[key]; const vb = b.dataset[key];
      const na = parseFloat(va); const nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
      return va.localeCompare(vb) * dir;
    });
    const tbody = document.querySelector('#files tbody');
    rows.forEach(r => tbody.appendChild(r));
  });
});
</script>
</body>
</html>
"""


def _level_class(level: str) -> str:
    return {
        "УЗ-1": "lvl-1",
        "УЗ-2": "lvl-2",
        "УЗ-3": "lvl-3",
        "УЗ-4": "lvl-4",
        "Без ПДн": "lvl-none",
    }.get(level, "lvl-none")


def _format_categories(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    parts = [f"{cat} ({n})" for cat, n in sorted(counts.items(), key=lambda x: -x[1])]
    return ", ".join(parts)


def write_html(reports: list[dict], summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    template = Template(_HTML_TEMPLATE)
    html = template.render(
        reports=reports,
        summary=summary,
        summary_json=json.dumps(summary, ensure_ascii=False),
        level_class=_level_class,
        format_categories=_format_categories,
    )
    path.write_text(html, encoding="utf-8")


# ---- Summary ----

def build_summary(reports: list[dict], elapsed: float) -> dict[str, Any]:
    total = len(reports)
    with_pii = sum(1 for r in reports if r.get("category_counts"))
    errors = sum(1 for r in reports if r.get("error"))

    cat_counter: Counter[str] = Counter()
    fmt_counter: Counter[str] = Counter()
    level_counter: Counter[str] = Counter()
    for r in reports:
        for k, v in r.get("category_counts", {}).items():
            cat_counter[k] += v
        ext = (r.get("extension") or "").lstrip(".") or "(без расш.)"
        fmt_counter[ext] += 1
        level_counter[r.get("protection_level", ProtectionLevel.NONE.value)] += 1

    # Гарантируем порядок УЗ
    ordered_levels: dict[str, int] = {}
    for lvl in ["УЗ-1", "УЗ-2", "УЗ-3", "УЗ-4", "Без ПДн"]:
        if lvl in level_counter:
            ordered_levels[lvl] = level_counter[lvl]

    return {
        "total_files": total,
        "files_with_pii": with_pii,
        "errors": errors,
        "elapsed_seconds": elapsed,
        "protection_level_counts": ordered_levels,
        "category_counts": dict(cat_counter),
        "format_counts": dict(fmt_counter),
    }
