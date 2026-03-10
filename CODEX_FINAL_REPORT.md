# 1. Что было сделано

Ниже — сводка по всем ключевым изменениям, которые были внесены в проект.

## Архитектура
- Проведена поэтапная декомпозиция перегруженного `scdlbot/__main__.py`.
- Вынесена pure-логика поиска/ранжирования в отдельный модуль `scdlbot/search_logic.py`.
- Вынесены runtime-хелперы в `scdlbot/runtime_ops.py`.
- Вынесены лимиты/допуск запросов/учёт активных задач в `scdlbot/runtime_limits.py`.
- Добавлен отдельный модуль для гигиены persistence: `scdlbot/persistence_hygiene.py`.
- Добавлен fail-fast валидатор конфигурации: `scdlbot/config_validation.py`.

## Поиск и quality fallback
- Улучшен разбор query из текста и ссылок (включая VK/Bandcamp кейсы).
- Добавлен многоступенчатый fallback: YouTube → платформенный поиск → web fallback.
- Добавлен более строгий title match для релевантности.
- Приоритизирован YouTube HD (по высоте видео) как сигнал качества источника.
- Добавлены форматтеры качества и более прозрачная логика scoring.

## Telegram UX
- Унифицированы русские команды/описания для разных scope и language.
- Добавлены/исправлены команды и кнопки (`/start`, `/help`, `/search`, `/dl`, `/link`, `/settings`, `/status`, `/jobs`, `/restart`).
- Добавлены owner-команды обслуживания persistence: `/persistence_info`, `/cleanup_persistence`.
- Улучшены тексты ошибок и сценарии устаревших inline-кнопок.

## Логирование и метрики
- Добавлен опциональный JSON-лог (`LOG_JSON`).
- Расширено структурированное логирование этапов pipeline с безопасным preview.
- Добавлены безопасные Telegram API-обёртки (`safe_send_message`, `safe_edit_message_text`, и т.д.).
- Добавлены/расширены runtime-метрики (uptime, monitor tick, last error, active jobs, rejected requests, restart/shutdown counters).
- Добавлен healthcheck endpoint (`/healthz`, `/readyz`).

## Graceful shutdown / restart
- Добавлен контролируемый shutdown с grace-периодом перед restart.
- Добавлен cooldown restart-запросов и marker-файл для защиты от restart-циклов.
- Улучшена видимость состояний shutdown/restart в логах и метриках.

## Rate limiting / anti-flood / concurrency
- Введены лимиты активных задач по user/chat/global.
- Добавлены cooldown и burst-контроль запросов.
- Добавлен реестр активных задач и owner-диагностика через `/jobs`.
- Снижены риски подвисаний/перегрузки event-loop за счёт admission control.

## Persistence / PicklePersistence cleanup
- PicklePersistence не заменён, но существенно усилен:
  - добавлена миграция состояния и маркер версии в `bot_data`;
  - добавлена безопасная startup-подготовка persistence-файла;
  - добавлен cleanup просроченных временных ключей;
  - добавлена recovery-модель с backup при повреждённом pickle, без «слепого удаления».
- Для временной callback-метадаты добавлены признаки ephemeral (`created_at`, `__ephemeral__`).

## CI
- Упрощён и стабилизирован GitHub Actions pipeline.
- Добавлен единый `make ci` для локального и CI smoke/compile/unit сценария.
- CI гоняется на Python 3.11 и 3.13.

## Тесты
- Добавлены unit-тесты для:
  - `search_logic.py`;
  - pure helper-функций `quality_fallback.py`;
  - runtime limits;
  - config validation;
  - persistence hygiene/migration/cleanup/recovery.
- Тесты детерминированные, без live Telegram API и без network dependency.

## Docker / systemd / deployment
- Добавлен generic `Dockerfile` для self-hosted/VPS запуска.
- Улучшен `Dockerfile.render`.
- Добавлены примеры `deploy/docker-compose.example.yml` и `deploy/scdlbot.service`.
- Обновлены операторские инструкции по запуску/обновлению/логам.

## env / preflight / docs
- Расширены `.env.sample` и `.env.cloud.sample`.
- Добавлены Python-level preflight/validation проверки.
- Обновлены `README.rst`, `CLOUD_SETUP.md`, `OPERATIONS.md`.
- Добавлен подробный `SEARCH_WORKFLOW.md` как карта пайплайна поиска.

# 2. Какие файлы были изменены

Ниже перечислены файлы, которые изменялись в процессе работ (по коду и эксплуатации), с пояснением «зачем файл нужен» и «что изменено».

- `scdlbot/__main__.py`
  - Зачем нужен: основной entrypoint и orchestration Telegram-бота.
  - Что поменялось: интеграция новых модулей логики/рантайма/лимитов/persistence, safe Telegram wrappers, команды `/status` `/jobs` `/restart` `/persistence_info` `/cleanup_persistence`, startup hardening, admission control, cleanup hooks, observability.

- `scdlbot/quality_fallback.py`
  - Зачем нужен: выбор/оценка качества источников и fallback-поиск.
  - Что поменялось: усилена quality/relevance логика, улучшен title matching, YouTube-focused сценарии, диагностические логи, исправления edge cases.

- `scdlbot/search_logic.py`
  - Зачем нужен: pure-логика построения query, ранжирования и форматирования для выбора источника.
  - Что поменялось: добавлен как выделенный модуль, реализованы helper-функции query usability/extraction/formatting/scoring и поиск high-quality источников.

- `scdlbot/runtime_ops.py`
  - Зачем нужен: runtime state, healthcheck, JSON logging, cleanup временных файлов, сводка executor.
  - Что поменялось: добавлен новый модуль и интегрирован в основной поток.

- `scdlbot/runtime_limits.py`
  - Зачем нужен: admission control, anti-flood, реестр активных задач, shutdown state.
  - Что поменялось: добавлен новый модуль и подключён к обработчикам запросов.

- `scdlbot/config_validation.py`
  - Зачем нужен: fail-fast валидация env/runtime-конфига и preflight.
  - Что поменялось: добавлен модуль, расширен список проверок (включая новые runtime/persistence параметры).

- `scdlbot/persistence_hygiene.py`
  - Зачем нужен: безопасная миграция/инспекция/очистка PicklePersistence.
  - Что поменялось: добавлен модуль с cleanup/migration/versioning/backup/atomic write.

- `tests/test_search_logic.py`
  - Зачем нужен: unit-покрытие pure search/query/ranking логики.
  - Что поменялось: добавлены edge-case тесты и ranking-проверки с mock/stub.

- `tests/test_quality_fallback_helpers.py`
  - Зачем нужен: unit-покрытие helper-логики quality fallback.
  - Что поменялось: добавлены тесты для title ratio, YouTube detection, floor checks, tie-breakers и `find_better_source`.

- `tests/test_runtime_limits.py`
  - Зачем нужен: проверка admission control и job tracking.
  - Что поменялось: добавлены тесты на лимиты/блокировки/shutdown.

- `tests/test_config_validation.py`
  - Зачем нужен: проверка корректности runtime env validation и redaction.
  - Что поменялось: добавлены тесты на обязательные поля, типы и ошибки конфигурации.

- `tests/test_persistence_hygiene.py`
  - Зачем нужен: проверка миграции, cleanup и recovery persistence-состояния.
  - Что поменялось: добавлены тесты на normal/corrupt startup сценарии.

- `.github/workflows/build.yml`
  - Зачем нужен: CI pipeline.
  - Что поменялось: упрощение и запуск через `make ci`, Python matrix 3.11/3.13.

- `Makefile`
  - Зачем нужен: стандартные команды сборки/проверки/запуска.
  - Что поменялось: добавлены/обновлены `ci`, `smoke_test`, `test_search_logic`, cloud-потоки.

- `Dockerfile`
  - Зачем нужен: контейнеризация для self-hosted/VPS.
  - Что поменялось: добавлен production-friendly образ с non-root user, ffmpeg, healthcheck, persistent paths.

- `Dockerfile.render`
  - Зачем нужен: Docker-сборка под Render.
  - Что поменялось: усилен healthcheck и runtime env.

- `deploy/docker-compose.example.yml`
  - Зачем нужен: быстрый пример запуска в Docker Compose.
  - Что поменялось: добавлен сервисный шаблон с volume/ports/env.

- `deploy/scdlbot.service`
  - Зачем нужен: systemd unit для Linux/VPS.
  - Что поменялось: добавлен рабочий пример с preflight и restart policy.

- `README.rst`
  - Зачем нужен: главный обзор проекта и запуск.
  - Что поменялось: добавлены ссылки на `CLOUD_SETUP.md`, `OPERATIONS.md`, deployment notes.

- `CLOUD_SETUP.md`
  - Зачем нужен: практический чеклист запуска в облаке.
  - Что поменялось: обновлены шаги bootstrap/preflight/dry-run/run и runtime safety notes.

- `OPERATIONS.md`
  - Зачем нужен: операторский runbook.
  - Что поменялось: добавлены health/metrics/limits/restart/persistence-инструкции, Docker/systemd разделы.

- `.env.sample`, `.env.cloud.sample`, `.env.flacbot.sample`
  - Зачем нужны: шаблоны env-конфигурации.
  - Что поменялось: расширены runtime/quality/limits/health/persistence переменные и дефолты.

- `render.yaml`, `scripts/cloud_preflight.sh`, `AGENTS.md`
  - Зачем нужны: cloud/deploy automation и правила работы.
  - Что поменялось: синхронизированы под новый production-hardening поток.

# 3. Какие новые файлы были добавлены

- `scdlbot/search_logic.py` — pure search/query/ranking логика.
- `scdlbot/runtime_ops.py` — runtime state, healthcheck, JSON logging, cleanup DL_DIR.
- `scdlbot/runtime_limits.py` — admission control, anti-flood, active jobs registry.
- `scdlbot/config_validation.py` — env/runtime validator + preflight helper.
- `scdlbot/persistence_hygiene.py` — миграция/инспекция/cleanup/recovery для PicklePersistence.
- `tests/test_search_logic.py` — unit-тесты search logic.
- `tests/test_quality_fallback_helpers.py` — unit-тесты quality fallback helpers.
- `tests/test_runtime_limits.py` — unit-тесты runtime limits.
- `tests/test_config_validation.py` — unit-тесты config validation.
- `tests/test_persistence_hygiene.py` — unit-тесты persistence hygiene.
- `OPERATIONS.md` — операторский runbook.
- `Dockerfile` — generic production Docker image.
- `deploy/docker-compose.example.yml` — docker-compose шаблон.
- `deploy/scdlbot.service` — systemd unit пример.

Примечание: временные служебные файлы (`1`, `2`, `TECH_REPORT_FOR_AI.md`) были удалены в ходе работ и не являются частью итогового состояния.

# 4. Как теперь работает бот

## Когда пользователь отправляет ссылку
1. Бот парсит URL из сообщения/подписи.
2. Проверяет допустимость домена и режим чата.
3. Формирует список кандидатов/прямых ссылок.
4. В зависимости от режима (`dl`/`ask`/`link`) либо сразу запускает скачивание, либо показывает выбор действия.
5. Перед тяжёлой задачей срабатывает admission control (лимиты/cooldown/burst).
6. Задача регистрируется в runtime реестре активных jobs.

## Когда пользователь отправляет текстовый запрос
1. Текст проходит проверку «достаточно ли он осмысленный для поиска».
2. Собирается нормализованный query.
3. Выполняется поисковый pipeline (YouTube/platform/web fallback, если включён).
4. Кандидаты пробируются по качеству и релевантности.
5. Если один явно лучший — бот сразу скачивает.
6. Если вариантов несколько — показывает inline-кнопки выбора.

## Как работает поиск лучших источников
- Сначала собираются кандидаты из быстрых источников (YouTube/platform search), далее опционально web fallback.
- Для каждого кандидата считается relevance (по токенам query/title/URL).
- Источники ранжируются по набору признаков (HD YouTube, match ratio, lossless, bitrate, sample rate, video height).

## Как работает quality fallback
- Если исходный источник плохого качества, бот пытается найти более качественный.
- Приоритет отдается lossless и/или YouTube HD при хорошем совпадении названия.
- Есть floor-условия (`QUALITY_MIN_BITRATE_KBPS`, `PREFER_LOSSLESS`), но учитывается и «лучше текущего».

## Когда показывается выбор через inline-кнопки
- Когда найдено несколько близких по релевантности/качеству вариантов.
- В `chat_data` сохраняется временный `search_choice:<token>` с TTL.
- Пользователь выбирает вариант, бот запускает скачивание выбранного URL.
- Просроченные варианты автоматически очищаются.

## Как происходит скачивание, конвертация, подпись и отправка
- Скачивание и тяжёлые операции уходят в background executor.
- Файл при необходимости конвертируется (ffmpeg), проверяется размер/формат.
- Формируется расширенная подпись (источник, исполнитель, трек, альбом, год, жанр, качество, формат, размер).
- Файл отправляется в Telegram (с fallback-обработкой TelegramError).

## Как работают настройки, статус, рестарт и админские команды
- `/settings` — чатовые настройки режима/поведения.
- `/status` — runtime snapshot (готовность, jobs, лимиты, health, uptime).
- `/jobs` — owner-only список активных задач.
- `/restart` — owner-only безопасный restart с grace-периодом и cooldown.
- `/persistence_info` — owner-only диагностика persistence.
- `/cleanup_persistence` — owner-only безопасная очистка только временных persistence-ключей.

# 5. Что теперь умеет бот по сравнению с предыдущей версией

## Улучшения
- Чище архитектура и лучше разделение ответственности.
- Сильнее и точнее поиск по ссылке/тексту.
- Более предсказуемый quality fallback.
- Появились runtime-команды для операторского контроля.
- Стало больше диагностических логов и метрик.
- Улучшены deployment-артефакты (Docker/systemd).
- Появился preflight validator конфигурации.
- Улучшена устойчивость persistence и безопасная очистка временного мусора.

## Что стало надёжнее/безопаснее/удобнее
- Меньше шансов «уронить» бота из-за сетевых/Telegram-ошибок.
- Меньше риска перегрузки при всплесках запросов.
- Безопаснее restart/shutdown.
- Проще наблюдать состояние в проде.
- Persistence больше не удаляется «в лоб» при первой ошибке чтения.

# 6. Какие переменные окружения теперь важны

Ниже — ключевые env-переменные (обязательность, default, назначение).

## Обязательные
- `TG_BOT_TOKEN` — обязательно, default: нет; токен Telegram-бота.
- `TG_BOT_OWNER_CHAT_ID` — обязательно для owner-команд, default: `0`; ID владельца.

## Режим и запуск
- `BOT_MODE` — опционально, default: `scdlbot`; выбор режима (`scdlbot`/`flacbot`).
- `WEBHOOK_ENABLE` — опционально, default: `0`; webhook vs polling.
- `HOST` / `PORT` — опционально, default: `127.0.0.1` / `5000`; bind для webhook.
- `WEBHOOK_APP_URL_ROOT` / `WEBHOOK_APP_URL_PATH` / `WEBHOOK_SECRET_TOKEN` — опционально (обязательны при webhook в проде).
- `TG_BOT_API`, `TG_BOT_API_LOCAL_MODE` — опционально; endpoint Telegram API и локальный режим.

## Производительность и executor
- `WORKERS` — опционально, default: `2`; число воркеров.
- `EXECUTOR_KIND` — опционально, default: `thread`; `thread`/`process`.
- `DL_TIMEOUT`, `CHECK_URL_TIMEOUT`, `COMMON_CONNECTION_TIMEOUT` — таймауты.

## Поиск и качество
- `QUALITY_MIN_BITRATE_KBPS` — default `320`; минимальный bitrate floor.
- `PREFER_LOSSLESS` — default `1`; стремиться к lossless.
- `ENABLE_CROSS_PLATFORM_SEARCH` — default `1`; межплатформенный поиск.
- `ENABLE_WEB_FALLBACK` — default `1`; web fallback.
- `FALLBACK_MAX_CANDIDATES` — default `8`; лимит кандидатов.
- `YOUTUBE_MIN_HEIGHT` — default `1080`; HD-порог YouTube.
- `SEARCH_RESULT_LIMIT` — default `5`; лимит вариантов.
- `SEARCH_CHOICE_TTL_SECONDS` — default `900`; TTL inline выбора.

## Admission / anti-flood / concurrency
- `MAX_ACTIVE_JOBS_PER_USER` — default `2`.
- `MAX_ACTIVE_JOBS_PER_CHAT` — default `4`.
- `MAX_GLOBAL_ACTIVE_JOBS` — default `8`.
- `USER_REQUEST_COOLDOWN_SECONDS` — default `3`.
- `CHAT_REQUEST_COOLDOWN_SECONDS` — default `1`.
- `BURST_REQUEST_LIMIT` — default `5`.
- `BURST_WINDOW_SECONDS` — default `20`.

## Persistence / restart safety
- `CHAT_STORAGE` — default `/tmp/scdlbot.pickle`; файл PicklePersistence.
- `PERSISTENCE_EPHEMERAL_TTL_SECONDS` — default `3600`; TTL для временной callback/request metadata.
- `RESTART_COOLDOWN_SECONDS` — default `30`; cooldown restart.
- `RESTART_STATE_FILE` — default `/tmp/scdlbot_restart_ts`; marker restart-запроса.
- `SHUTDOWN_GRACE_SECONDS` — default `10`; ожидание завершения активных задач.

## Файлы/ресурсы
- `DL_DIR` — default `/tmp/scdlbot`; рабочая папка скачиваний.
- `TEMP_FILE_TTL_SECONDS` — default `86400`; чистка старых temp файлов.
- `DL_DIR_MAX_BYTES`, `DL_DIR_MAX_FILE_COUNT` — default `0`; опциональные quota.
- `MAX_TG_FILE_SIZE`, `MAX_CONVERT_FILE_SIZE` — лимиты обработки/отправки.
- `COOKIES_FILE` — опционально; cookies для источников.

## Наблюдаемость
- `LOGLEVEL` — default `INFO`.
- `LOG_JSON` — default `0`.
- `METRICS_HOST`, `METRICS_PORT` — default `127.0.0.1:8000`.
- `HEALTHCHECK_ENABLE`, `HEALTHCHECK_HOST`, `HEALTHCHECK_PORT` — health endpoint.
- `SYSLOG_ADDRESS`, `HOSTNAME` — опционально для внешнего логирования.

## Сетевые и whitelist/blacklist (опционально)
- `PROXIES`, `SOURCE_IPS`, `NO_FLOOD_CHAT_IDS`.
- `WHITELIST_DOMAINS`, `BLACKLIST_DOMAINS`.
- `WHITELIST_CHATS`, `BLACKLIST_CHATS`.

# 7. Как запускать проект сейчас

## Локальный запуск
1. `cp .env.sample .env`
2. Заполнить минимум: `TG_BOT_TOKEN`, `TG_BOT_OWNER_CHAT_ID`
3. `poetry install --with main,dev,docs,flacbot --sync`
4. `make preflight`
5. `make run` (или `python -m scdlbot`)

## Poetry/Make команды
- `make test_fast` — быстрые проверки в цикле разработки.
- `make smoke_test` — быстрый unittest прогон.
- `make ci` — compile + import smoke + unit tests.
- `make cloud_preflight`, `make cloud_dry_run`, `make cloud_run` — cloud-поток.

## Docker запуск
1. `cp .env.sample .env`
2. Заполнить env.
3. `docker compose -f deploy/docker-compose.example.yml up -d --build`
4. Проверить `http://127.0.0.1:8080/healthz`

## systemd запуск
1. Скопировать `deploy/scdlbot.service` в `/etc/systemd/system/scdlbot.service`
2. Подготовить `/etc/scdlbot/scdlbot.env`
3. `sudo systemctl daemon-reload`
4. `sudo systemctl enable --now scdlbot`
5. Проверить `sudo systemctl status scdlbot` и `journalctl -u scdlbot -f`

## Что проверить перед стартом
- корректный `TG_BOT_TOKEN`;
- что не запущен второй polling-инстанс с тем же токеном;
- что `CHAT_STORAGE` и `DL_DIR` доступны на запись;
- что доступен `ffmpeg`;
- что preflight проходит без ошибок.

# 8. Что покрыто тестами

## Добавленные тесты
- `tests/test_search_logic.py`:
  - extraction query из URL/текста;
  - usability фильтры;
  - форматтеры quality/source;
  - ranking/dedup в поиске.

- `tests/test_quality_fallback_helpers.py`:
  - `compute_title_match_ratio`;
  - `_is_youtube_url`;
  - `_meets_floor`;
  - `_is_candidate_better`;
  - поведение `find_better_source` в mock-сценариях.

- `tests/test_runtime_limits.py`:
  - admission decision, лимиты и shutdown-блокировки.

- `tests/test_config_validation.py`:
  - валидация env, redaction/sanitize.

- `tests/test_persistence_hygiene.py`:
  - migration/version marker;
  - cleanup ephemeral keys;
  - inspect summary;
  - startup recovery с backup при corrupt pickle.

## Что осталось без тестов
- Живые Telegram API сценарии (осознанно не покрыты unit-тестами).
- Реальные network-поиски/внешние сайты (yt-dlp/web requests) end-to-end.
- Полный e2e media pipeline в боевых условиях (зависит от внешних платформ и сети).

# 9. Что сделано в CI

CI теперь автоматически делает:
1. matrix по Python `3.11` и `3.13`;
2. установку Poetry и зависимостей;
3. запуск `make ci`, где выполняется:
   - `py_compile` ключевых модулей;
   - import smoke (`import scdlbot...`);
   - unit tests (`unittest discover`).

Итог: CI стал легче, быстрее и лучше синхронизирован с локальной командой проверки.

# 10. Известные ограничения и риски

- Внешние источники нестабильны: сайты/форматы/anti-bot могут ломать extraction.
- При сильной нагрузке возможны очереди и delayed responses, даже с лимитами.
- `__main__.py` всё ещё большой: декомпозиция сделана, но файл остаётся центральным и сложным.
- Есть риск роста `CHAT_STORAGE`, если появятся новые временные ключи без TTL политики.
- Webhook-конфигурация чувствительна к неправильным URL/ingress.
- Некоторые ветки отправки медиа по-прежнему трудно полноценно тестировать без живого Telegram.

# 11. Что я рекомендую сделать следующим шагом

Приоритетный список:
1. Вынести media post-processing helpers (`build_track_caption`, thumbnail logic) в отдельный pure-модуль.
2. Добавить targeted unit-тесты для caption/metadata helpers.
3. Добавить интеграционный dry-run тест для admission + scheduling (без реального Telegram).
4. Укрепить миграции persistence: предусмотреть версию `2` и формализованный changelog миграций.
5. Добавить периодическую авто-очистку persistence (по расписанию) с ограничением времени выполнения.
6. Добавить алерты по метрикам (рост rejected requests, постоянный backlog jobs, ошибки health).
7. Улучшить user-facing сообщения при quality fallback (более точные причины отказа).
8. Подготовить небольшой runbook disaster-recovery (что делать при битом pickle, как откатывать backup).
9. Добавить optional feature-flag для более агрессивного YouTube-first режима.
10. Постепенно сокращать ответственность `__main__.py` без изменения поведения.

---

## Итоговая готовность проекта
Проект в рабочем production-ready состоянии для cloud/VPS запуска с заметно более устойчивой runtime-моделью, безопаснее настроенным persistence и понятным операторским контуром.

## Что уже хорошо
- Есть базовая наблюдаемость (логи, метрики, health).
- Есть admission control и graceful restart/shutdown.
- Есть Docker/systemd шаблоны.
- Есть preflight/validation и unit-покрытие ключевой pure-логики.

## Что ещё желательно доделать
- Дальше уменьшать размер `__main__.py`.
- Добавить больше интеграционных тестов без внешней сети.
- Развивать стратегию миграций persistence на будущие версии.
