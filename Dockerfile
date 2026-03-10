FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    BOT_MODE=scdlbot \
    DL_DIR=/var/lib/scdlbot/downloads \
    CHAT_STORAGE=/var/lib/scdlbot/state/scdlbot.pickle \
    HEALTHCHECK_ENABLE=1 \
    HEALTHCHECK_HOST=0.0.0.0 \
    HEALTHCHECK_PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN pip install --upgrade pip poetry \
    && poetry install --with main,flacbot --sync --no-interaction --no-ansi

COPY . .

RUN useradd --uid 10001 --create-home scdlbot \
    && mkdir -p /var/lib/scdlbot/downloads /var/lib/scdlbot/state \
    && chown -R scdlbot:scdlbot /app /var/lib/scdlbot

USER scdlbot

EXPOSE 5000 8000 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import os,sys,urllib.request; \
enabled=os.getenv('HEALTHCHECK_ENABLE','1') in {'1','true','True','yes','on'}; \
port=os.getenv('HEALTHCHECK_PORT','8080'); \
sys.exit(0) if not enabled else sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=3).status==200 else 1)"

CMD ["python", "-m", "scdlbot"]
