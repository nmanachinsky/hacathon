FROM python:3.11-slim AS base

# Системные зависимости для парсинга и OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-rus \
        tesseract-ocr-eng \
        poppler-utils \
        ffmpeg \
        antiword \
        libreoffice-core \
        libreoffice-writer \
        libxml2 \
        libxslt1.1 \
        libgomp1 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# uv (быстрый менеджер пакетов)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Сначала только манифесты — для кэша слоёв
COPY pyproject.toml ./
COPY README.md ./

# Базовые runtime-зависимости + OCR
RUN uv venv && uv pip install --no-cache \
        -e ".[ocr]"

# Копируем код
COPY src ./src
COPY config ./config
COPY scripts ./scripts

ENV PYTHONUNBUFFERED=1 \
    PII_INPUT=/data \
    PII_OUTPUT=/reports

VOLUME ["/data", "/reports"]

ENTRYPOINT ["uv", "run", "pii-scan"]
CMD ["scan", "--input", "/data", "--output", "/reports"]
