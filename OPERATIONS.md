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

Для локального smoke-запуска:
- `make preflight`
- `make run`

## 3) Polling vs Webhook

- `WEBHOOK_ENABLE=0` -> polling
- `WEBHOOK_ENABLE=1` -> webhook

Для polling:
- запускать только **один** инстанс на один `TG_BOT_TOKEN`

Для webhook:
- убедиться, что заполнены `WEBHOOK_APP_URL_ROOT` и корректный `PORT/HOST`

## 3.1) Single-instance правило

- Для одного `TG_BOT_TOKEN` держите только один активный polling-воркер.
- Для webhook также рекомендуется один активный runtime-инстанс, если не настроена внешняя координация.

## 4) Healthcheck и metrics

Если `HEALTHCHECK_ENABLE=1`:
- `GET /healthz` — общая health-сигнализация
- `GET /readyz` — readiness

Prometheus:
- `METRICS_HOST`, `METRICS_PORT`
- доступны runtime-метрики по job/admission/shutdown

## 4.1) Логи

- Docker: `docker logs -f scdlbot`
- systemd: `journalctl -u scdlbot -f`
- Cloud process manager: используйте встроенный log stream платформы

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
- `/persistence_info` — owner-only сводка по файлу persistence и временным ключам
- `/cleanup_persistence` — owner-only безопасная очистка временных persistence-ключей
- `/restart` — owner-only безопасный restart с grace-периодом

## 7.1) PicklePersistence hygiene

Что хранится в `CHAT_STORAGE`:
- durable: пользовательские настройки чата (`settings`)
- ephemeral: `search_choice:*` и временные callback/request-метаданные (ключи вида message_id)

Что безопасно чистить:
- просроченные `search_choice:*` (`SEARCH_CHOICE_TTL_SECONDS`)
- просроченные временные callback/request-метаданные (`PERSISTENCE_EPHEMERAL_TTL_SECONDS`)

Когда запускать cleanup:
- вручную через `/cleanup_persistence`, если файл persistence растёт из-за временных ключей
- автоматически cleanup выполняется на старте и в runtime cleanup-хуках

Поведение при повреждённом pickle:
- файл не удаляется вслепую
- создаётся backup `*.corrupt.*.bak`
- бот стартует с чистым persistence-файлом, сохранив backup для разбирательства

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

## 9) Docker deployment (VPS / self-hosted)

Файлы:
- `Dockerfile` (generic runtime)
- `deploy/docker-compose.example.yml`

Шаги:
1. `cp .env.sample .env` и заполнить значения.
2. `docker compose -f deploy/docker-compose.example.yml up -d --build`
3. Проверить health: `curl http://127.0.0.1:8080/healthz`

Рекомендации:
- Пробрасывайте persistent volume для `/var/lib/scdlbot` (там `DL_DIR` и `CHAT_STORAGE`).
- Не запускайте второй контейнер с тем же токеном в polling-режиме.

## 10) systemd deployment (VPS)

Файл unit:
- `deploy/scdlbot.service`

Рекомендуемое размещение:
- Код: `/opt/scdlbot`
- Environment file: `/etc/scdlbot/scdlbot.env`
- Persistent storage: `/var/lib/scdlbot/downloads`, `/var/lib/scdlbot/state`

Шаги:
1. Скопировать unit-файл в `/etc/systemd/system/scdlbot.service`.
2. Создать env-файл `/etc/scdlbot/scdlbot.env`.
3. Выполнить:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now scdlbot`
4. Проверка:
   - `sudo systemctl status scdlbot`
   - `journalctl -u scdlbot -f`

## 11) Обновление / restart flow

1. Обновить код (`git pull`).
2. Обновить зависимости при необходимости (`poetry install --with main,flacbot --sync`).
3. Прогнать preflight (`poetry run python -m scdlbot.config_validation --preflight`).
4. Перезапустить сервис:
   - systemd: `sudo systemctl restart scdlbot`
   - Docker compose: `docker compose -f deploy/docker-compose.example.yml up -d --build`
