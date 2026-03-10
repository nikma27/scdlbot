# 1. Текущее состояние проекта

Проект запускается как Python Telegram-бот (`python -m scdlbot`) через Poetry/Make, поддерживает polling и webhook, имеет health/readiness endpoint, Prometheus metrics, admission limits, graceful restart и runtime-команды оператора.

После последних правок бот корректно поддерживает **ephemeral cloud режим** (без постоянного диска): рабочие файлы и persistence могут жить в `/tmp`, а при рестарте инстанса состояние может безопасно потеряться.

# 2. Что мешало или могло мешать облачному запуску

1. Жёсткая зависимость от writable `CHAT_STORAGE`/`DL_DIR` в preflight: при недоступном пути был hard fail, хотя можно безопасно fallback в `/tmp`.
2. Потенциальный runtime-сбой при недоступном `CHAT_STORAGE`/`DL_DIR`: путь задавался из env без безопасного fallback.
3. Импортный крэш в cloud dry-run при пустых env-списках:
   - `NO_FLOOD_CHAT_IDS=""`
   - `WHITELIST_CHATS=""`
   - `BLACKLIST_CHATS=""`
4. Недостаточно явное описание в доках, что `/tmp` — нормальный сценарий для ephemeral cloud и что persistence не переживает рестарт.

# 3. Что ты изменил

## Код
- `scdlbot/__main__.py`
  - Добавлен безопасный парсинг int-списков env (`_env_int_list`).
  - Исправлен парсинг `NO_FLOOD_CHAT_IDS`, `WHITELIST_CHATS`, `BLACKLIST_CHATS` (пустые/битые значения больше не валят импорт).
  - Добавлен runtime fallback путей хранения:
    - `CHAT_STORAGE` -> `CHAT_STORAGE_FALLBACK` (по умолчанию `/tmp/scdlbot.pickle`)
    - `DL_DIR` -> `DL_DIR_FALLBACK` (по умолчанию `/tmp/scdlbot`)
  - Добавлен helper `apply_cloud_storage_fallbacks()` и запуск его до config validation.
  - В startup summary добавлены fallback-поля и флаг `ephemeral_storage`.
  - В `/persistence_info` добавлены путь storage и явный режим (`ephemeral (/tmp)`).

- `scdlbot/config_validation.py`
  - Валидация `CHAT_STORAGE` и `DL_DIR` переведена на cloud-friendly логику:
    - если основной путь не writable, но fallback writable -> warning (не error);
    - error только если недоступны и основной путь, и fallback.
  - Добавлены `CHAT_STORAGE_FALLBACK` и `DL_DIR_FALLBACK` в parsed env defaults.

## Тесты
- `tests/test_config_validation.py`
  - Добавлен тест, что при недоступных storage путях и доступном `/tmp` preflight проходит с warning и без hard fail.

## Конфиг и документация
- `.env.sample`, `.env.cloud.sample`
  - Добавлены и задокументированы:
    - `CHAT_STORAGE_FALLBACK`
    - `DL_DIR_FALLBACK`
  - Явно отмечен поддерживаемый ephemeral cloud сценарий через `/tmp`.

- `CLOUD_SETUP.md`
  - Добавлено явное пояснение про fallback в `/tmp` и непостоянство состояния.

- `OPERATIONS.md`
  - Добавлен отдельный блок про ephemeral cloud без постоянного диска.
  - Уточнены рекомендации для Docker/systemd: persistent volume опционален, `/tmp` допустим для ephemeral режима.

# 4. Как теперь проект работает в облаке без постоянного local storage

- Основные runtime-файлы могут храниться только временно:
  - `CHAT_STORAGE` (pickle state)
  - `DL_DIR` (скачанные/промежуточные файлы)
  - marker restart (`RESTART_STATE_FILE`, обычно `/tmp/...`)

- Если заданный путь хранения недоступен, бот автоматически пытается перейти на fallback (`/tmp` по умолчанию).

- При рестарте инстанса:
  - persistence/state может исчезнуть (это ожидаемо в ephemeral среде);
  - бот стартует безопасно заново;
  - временные кеши выбора/колбэков и чатовые настройки могут сброситься;
  - это считается нормальным graceful degradation.

- На что можно рассчитывать:
  - на работу бота в текущем runtime;
  - на безопасный startup без «обязательного постоянного диска».

- На что нельзя рассчитывать:
  - на долговечность `PicklePersistence` между рестартами инстанса.

# 5. Минимальный env для облачного запуска

Минимально необходимые переменные:

1. `TG_BOT_TOKEN` — обязательно.
2. `TG_BOT_OWNER_CHAT_ID` — желательно обязательно (owner-команды и обслуживание).
3. `BOT_MODE=scdlbot` — явно указать режим.
4. `WEBHOOK_ENABLE` — `0` (polling) или `1` (webhook).
5. Для webhook обязательно:
   - `WEBHOOK_APP_URL_ROOT`
   - `HOST`
   - `PORT`

Рекомендуемые для ephemeral cloud:

- `CHAT_STORAGE=/tmp/scdlbot.pickle`
- `CHAT_STORAGE_FALLBACK=/tmp/scdlbot.pickle`
- `DL_DIR=/tmp/scdlbot`
- `DL_DIR_FALLBACK=/tmp/scdlbot`
- `TEMP_FILE_TTL_SECONDS` (например `86400` или меньше)
- `HEALTHCHECK_ENABLE=1`, `HEALTHCHECK_HOST=0.0.0.0`, `HEALTHCHECK_PORT=8080`
- `METRICS_HOST`, `METRICS_PORT`

# 6. Пошаговый запуск в облаке

1. Установка зависимостей:
   - `bash ./cloud_startup.sh`
2. Подготовка env:
   - `cp .env.cloud.sample .env.cloud`
   - заполнить минимум `TG_BOT_TOKEN`, `TG_BOT_OWNER_CHAT_ID`
3. Preflight:
   - `make cloud_preflight`
4. Dry-run (без polling/webhook):
   - `make cloud_dry_run`
5. Реальный запуск:
   - `make cloud_run`

# 7. Что проверить сразу после деплоя

1. Логи старта:
   - есть `config validation passed`
   - есть startup summary
   - нет циклических crash/restart

2. Health/ready:
   - `GET /healthz`
   - `GET /readyz`

3. Базовые команды:
   - `/status`
   - `/jobs` (owner)
   - `/persistence_info` (owner)
   - `/cleanup_persistence` (owner)
   - `/restart` (owner)

4. Метрики:
   - endpoint на `METRICS_HOST:METRICS_PORT`

# 8. Что осталось ограничением или риском

1. Без постоянного storage состояние `PicklePersistence` не гарантировано между рестартами.
2. При очень активной нагрузке временный `DL_DIR` всё равно требует контроля TTL/лимитов.
3. Внешние источники (YouTube/SC/BC и т.д.) могут менять поведение и периодически ломать extraction.
4. Для `make run` нужен валидный токен и доступ к Telegram API; с dummy token startup завершается ожидаемой ошибкой `getMe`.
5. `__main__.py` остаётся большим — это техдолг, но не блокер cloud-запуска.

# 9. Итог

Проект **готов к облачному запуску в ephemeral-среде** при условии корректного env и валидного Telegram токена.

Критических блокеров для сценария «без постоянного локального диска» после правок не осталось: есть fallback на `/tmp`, безопасная деградация persistence, рабочий cloud preflight и cloud dry-run.

Что осталось делать дальше (не блокирует запуск):
- продолжить декомпозицию `__main__.py`;
- добавить ещё интеграционных тестов runtime-сценариев без live Telegram;
- при необходимости перейти на внешнее долговременное state-хранилище (если понадобится устойчивость state между рестартами).
