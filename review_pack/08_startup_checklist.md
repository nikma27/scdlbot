# Startup checklist (коротко)

1. **Подготовить `.env`**
   - `cp .env.sample .env`
   - Заполнить минимум: `TG_BOT_TOKEN`, `TG_BOT_OWNER_CHAT_ID`
   - При webhook: дополнить `WEBHOOK_*`, `HOST`, `PORT`

2. **Команда запуска**
   - Установить зависимости: `poetry install --with main,dev,docs,flacbot --sync`
   - Проверить конфиг: `make preflight`
   - Запуск: `make run` (или `poetry run python -m scdlbot`)

3. **Что проверить после старта**
   - В логах нет ошибок валидации и токена.
   - Бот отвечает на `/start` и `/status`.
   - В polling-режиме запущен только один инстанс на токен.

4. **Что проверить в первую очередь**
   - Команды: `/status`, `/jobs` (owner), `/persistence_info` (owner)
   - При необходимости: `/cleanup_persistence` (owner), `/restart` (owner)
   - Health endpoints (если включены): `/healthz`, `/readyz`
   - Метрики: endpoint на `METRICS_HOST:METRICS_PORT`
