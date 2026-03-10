# scdlbot Operations Notes

Короткий runbook для production-эксплуатации.

## 1) Обязательные переменные

- `TG_BOT_TOKEN` (обязательно)
- `TG_BOT_OWNER_CHAT_ID` (обязательно для owner-команд `/restart`, `/jobs`)

Рекомендуется также задать:
- `BOT_MODE` (`scdlbot` или `flacbot`)
- `WORKERS`, `EXECUTOR_KIND`
- `DL_DIR`, `CHAT_STORAGE`
- `LOGLEVEL`, `LOG_JSON`
- `HEALTHCHECK_ENABLE`, `HEALTHCHECK_HOST`, `HEALTHCHECK_PORT`
- `METRICS_HOST`, `METRICS_PORT`

## 2) Рекомендуемая последовательность запуска

1. `bash ./cloud_startup.sh`
2. `cp .env.cloud.sample .env.cloud` и заполнить значения
3. `make cloud_preflight`
4. `make cloud_dry_run`
5. `make cloud_run`

## 3) Polling vs Webhook

- `WEBHOOK_ENABLE=0` -> polling
- `WEBHOOK_ENABLE=1` -> webhook

Для polling:
- запускать только **один** инстанс на один `TG_BOT_TOKEN`

Для webhook:
- убедиться, что заполнены `WEBHOOK_APP_URL_ROOT` и корректный `PORT/HOST`

## 4) Healthcheck и metrics

Если `HEALTHCHECK_ENABLE=1`:
- `GET /healthz` — общая health-сигнализация
- `GET /readyz` — readiness

Prometheus:
- `METRICS_HOST`, `METRICS_PORT`
- доступны runtime-метрики по job/admission/shutdown

## 5) Runtime safety controls

### Admission / limits

- `MAX_ACTIVE_JOBS_PER_USER`
- `MAX_ACTIVE_JOBS_PER_CHAT`
- `MAX_GLOBAL_ACTIVE_JOBS`

### Anti-flood

- `USER_REQUEST_COOLDOWN_SECONDS`
- `CHAT_REQUEST_COOLDOWN_SECONDS`
- `BURST_REQUEST_LIMIT`
- `BURST_WINDOW_SECONDS`

### Shutdown / restart

- `SHUTDOWN_GRACE_SECONDS`
- `RESTART_COOLDOWN_SECONDS`

## 6) Disk hygiene

- `TEMP_FILE_TTL_SECONDS` — удаление старых temp entry в `DL_DIR`
- `DL_DIR_MAX_BYTES` — лимит общего объёма (0 = выключено)
- `DL_DIR_MAX_FILE_COUNT` — лимит числа файлов (0 = выключено)

Очистка выполняется на старте и в monitor callback.

## 7) Операторские команды

- `/status` — компактный runtime snapshot
- `/jobs` — owner-only список активных задач
- `/restart` — owner-only безопасный restart с grace-периодом

## 8) Частые проблемы и чеклист

1. Бот не стартует:
   - проверить `TG_BOT_TOKEN`
   - запустить `make cloud_preflight`
2. Webhook не принимает апдейты:
   - проверить `WEBHOOK_ENABLE=1`, `WEBHOOK_APP_URL_ROOT`, ingress
3. Очередь перегружена:
   - проверить `MAX_*_JOBS` и `WORKERS`
4. Много отказов по rate/admission:
   - ослабить `*_COOLDOWN_SECONDS` и `BURST_*` с осторожностью
5. Растёт диск:
   - проверить `DL_DIR`, `TEMP_FILE_TTL_SECONDS`, `DL_DIR_MAX_*`
