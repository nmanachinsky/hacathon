# PII Scanner

Автоматическое обнаружение персональных данных (152-ФЗ) в файловых хранилищах.

Сканирует разнородную файловую структуру (PDF, DOCX, DOC, RTF, XLS/XLSX, HTML, CSV, JSON, Parquet, изображения, видео), извлекает текст, детектирует ПДн по категориям 152-ФЗ, классифицирует файлы по уровням защищённости (УЗ-1…УЗ-4) и формирует отчёты в форматах CSV / JSON / Markdown / HTML-дашборд.

## Ключевые возможности

- **Гибридная детекция**: regex + алгоритмические валидаторы (Луна для карт, контрольные суммы СНИЛС/ИНН/БИК/счёта) + контекстный скоринг + опциональный NER (Natasha).
- **Поддержка всех заявленных форматов** + видео (через ffmpeg + OCR ключевых кадров).
- **Параллельная обработка** через ProcessPoolExecutor.
- **Дедупликация** по xxhash содержимого — одинаковые файлы сканируются один раз.
- **Стрим** для больших CSV/Parquet/JSON.
- **OCR** для изображений и сканов PDF (Tesseract `rus+eng`, при наличии в системе).
- **Безопасная выдача**: все значения маскируются, сохраняется SHA-256 хэш оригинала.
- **HTML-дашборд** с фильтрами, сортировкой и графиками (Chart.js).
- **Docker-сборка** — одна команда для запуска.

См. подробнее в [docs/APPROACH.md](docs/APPROACH.md).

## Быстрый старт

### Через uv (локально)

```bash
# Установка зависимостей
uv sync

# Предварительный анализ датасета
uv run python scripts/analyze_dataset.py --input ./data/share --output docs/DATASET_REPORT.md

# Запуск сканирования
uv run pii-scan scan --input ./data/share --output ./reports

# Опции
uv run pii-scan scan \
    --input ./data/share \
    --output ./reports \
    --workers 8 \
    --ocr auto \           # auto | always | off
    --ner / --no-ner \
    --formats csv,json,md,html
```

После сканирования откройте `reports/report.html` в браузере для интерактивного дашборда.

### Через Docker

```bash
docker compose build
docker compose run --rm scanner
# артефакты появятся в ./reports
```

Переменные окружения:
- `WORKERS` — число параллельных воркеров (default 8)
- `OCR_MODE` — `auto | always | off` (default `auto`)

## CLI-команды

| Команда | Назначение |
|---------|------------|
| `pii-scan scan -i DIR -o OUT` | Полное сканирование |
| `pii-scan analyze -i DIR -o file.md` | Только статистика по датасету |
| `pii-scan report --from report.json -o OUT` | Перегенерация отчётов из существующего JSON |

## Конфигурация

Все настройки — в [`config/default.yaml`](config/default.yaml). Можно подменить через `--config path/to/file.yaml`.

Ключевые параметры:

```yaml
scan:
  workers: 8
  enable_dedup: true

detect:
  min_confidence: 0.6
  use_ner: true

classification:
  state_id_large_count: 10        # порог «большого объёма» госидентификаторов
  regular_pii_large_count: 50     # порог «большого объёма» обычных ПДн

reporting:
  masking: partial                # full | partial | hash_only
```

## Артефакты сканирования

| Файл | Содержимое |
|------|------------|
| `reports/report.csv` | Формат строго по ТЗ: `путь,категории_ПДн,количество_находок,УЗ,формат_файла,рекомендации` |
| `reports/report.json` | Машиночитаемый отчёт со всеми находками (с маскированием + SHA-256) |
| `reports/report.md` | Executive summary |
| `reports/report.html` | Интерактивный дашборд |

## Системные зависимости (для OCR)

Опциональны, но рекомендуются:

```bash
# macOS
brew install tesseract tesseract-lang poppler ffmpeg antiword

# Ubuntu / Debian
sudo apt-get install tesseract-ocr tesseract-ocr-rus poppler-utils ffmpeg antiword libreoffice
```

В Docker-образе все зависимости уже установлены.

## Разработка и тесты

```bash
uv sync
uv run pytest -q
uv run ruff check src tests
```

## Поддерживаемые категории ПДн

- **Обычные**: ФИО, телефон, email, дата рождения, адрес.
- **Госидентификаторы**: паспорт РФ, СНИЛС, ИНН (физ./юр.), ВУ, MRZ, ОГРН.
- **Платёжные**: банковская карта, расчётный счёт, БИК, CVV.
- **Биометрия**: упоминания биометрических данных.
- **Специальные**: здоровье, религия, политика, расовая/национальная принадлежность.

## Лицензия и этика

Решение разработано в рамках хакатона. Все обнаруженные ПДн **маскируются** перед записью в артефакты — оригинальные значения никогда не сохраняются. Сохраняется только хэш SHA-256 для возможной трассируемости.
