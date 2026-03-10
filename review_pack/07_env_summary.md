# Ключевые env-переменные

## 1) Обязательные
- `TG_BOT_TOKEN` — токен Telegram-бота (без него бот не стартует).
- `TG_BOT_OWNER_CHAT_ID` — ID владельца для owner-команд (`/restart`, `/jobs`, `/persistence_info`, `/cleanup_persistence`).

## 2) Важные runtime-переменные
- `BOT_MODE` — режим запуска (`scdlbot`/`flacbot`).
- `WORKERS` — количество worker-задач.
- `EXECUTOR_KIND` — тип executor (`thread`/`process`).
- `DL_TIMEOUT`, `CHECK_URL_TIMEOUT`, `COMMON_CONNECTION_TIMEOUT` — сетевые и рабочие таймауты.
- `QUALITY_MIN_BITRATE_KBPS`, `PREFER_LOSSLESS` — floor качества и приоритет lossless.
- `ENABLE_CROSS_PLATFORM_SEARCH`, `ENABLE_WEB_FALLBACK` — fallback-поиск по платформам/вебу.
- `FALLBACK_MAX_CANDIDATES`, `SEARCH_RESULT_LIMIT`, `YOUTUBE_MIN_HEIGHT` — ограничения и приоритеты поиска.
- `SEARCH_CHOICE_TTL_SECONDS` — TTL временных inline-вариантов поиска.
- `MAX_ACTIVE_JOBS_PER_USER`, `MAX_ACTIVE_JOBS_PER_CHAT`, `MAX_GLOBAL_ACTIVE_JOBS` — лимиты параллельных задач.
- `USER_REQUEST_COOLDOWN_SECONDS`, `CHAT_REQUEST_COOLDOWN_SECONDS`, `BURST_REQUEST_LIMIT`, `BURST_WINDOW_SECONDS` — anti-flood и burst-контроль.
- `DL_DIR`, `MAX_TG_FILE_SIZE`, `MAX_CONVERT_FILE_SIZE`, `TEMP_FILE_TTL_SECONDS`, `DL_DIR_MAX_BYTES`, `DL_DIR_MAX_FILE_COUNT` — файловые лимиты и гигиена временных данных.

## 3) Persistence / restart
- `CHAT_STORAGE` — путь к файлу `PicklePersistence`.
- `PERSISTENCE_EPHEMERAL_TTL_SECONDS` — TTL временных persistence-ключей callback/request.
- `RESTART_COOLDOWN_SECONDS` — cooldown между restart-запросами.
- `RESTART_STATE_FILE` — marker-файл для restart safety между рестартами.
- `SHUTDOWN_GRACE_SECONDS` — сколько ждать завершения активных задач перед restart/shutdown.

## 4) Observability / health / metrics
- `LOGLEVEL` — уровень логирования.
- `LOG_JSON` — формат логов (`0` plain, `1` JSON).
- `METRICS_HOST`, `METRICS_PORT` — endpoint Prometheus-метрик.
- `HEALTHCHECK_ENABLE`, `HEALTHCHECK_HOST`, `HEALTHCHECK_PORT` — HTTP health/readiness endpoints.
- `SYSLOG_ADDRESS`, `HOSTNAME` — параметры внешнего syslog (если используется).

## 5) Webhook / Telegram API (если нужен webhook)
- `WEBHOOK_ENABLE` — переключение polling/webhook.
- `HOST`, `PORT` — bind адрес/порт.
- `WEBHOOK_APP_URL_ROOT`, `WEBHOOK_APP_URL_PATH`, `WEBHOOK_SECRET_TOKEN` — публичный webhook URL и секрет.
- `TG_BOT_API`, `TG_BOT_API_LOCAL_MODE` — адрес Telegram Bot API и локальный режим.
