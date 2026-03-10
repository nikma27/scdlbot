# Руководство владельца бота

Детальное руководство по текущему состоянию проекта и управлению ботом.

---

## 1. Текущий этап проекта

### Что готово

| Компонент | Статус | Описание |
|-----------|--------|----------|
| Конфигурация | ✅ | `.env.cloud` с токеном и `TG_BOT_OWNER_CHAT_ID` |
| Зависимости | ✅ | Poetry, FFmpeg, yt-dlp, scdl, bandcamp-dl |
| Режим запуска | ✅ | Polling (без webhook) |
| Ephemeral storage | ✅ | `/tmp` — данные не сохраняются между рестартами VM |
| Health endpoint | ✅ | `http://127.0.0.1:8080/healthz` |
| Owner-команды | ✅ | `/restart`, `/jobs`, `/status`, `/persistence_info`, `/cleanup_persistence` |

### Что может потребовать внимания (необязательно)

| Вопрос | Рекомендация |
|--------|--------------|
| Токен был показан в чате | Отозвать через @BotFather (`/revoke`) и создать новый, обновить `.env.cloud` |
| Ephemeral = данные теряются при остановке VM | Нормально для dev/тест. Для prod — persistent volume или Docker/systemd |
| Один инстанс на токен | Не запускай второй `make cloud_run` с тем же токеном |

### Правки перед продакшеном (если планируется)

1. **Токен:** получить новый в @BotFather (если старый утекал).
2. **Webhook:** при деплое на Render/VPS с доменом — включить `WEBHOOK_ENABLE=1`, заполнить `WEBHOOK_APP_URL_ROOT`, `WEBHOOK_SECRET_TOKEN`.
3. **Persistent storage:** для долгой работы — заменить `/tmp` на `/var/lib/scdlbot` и пробросить volume.

**Вывод:** проект готов к работе в текущей конфигурации (ephemeral cloud, polling). Специальные правки нужны только при переходе на prod/webhook или persistent storage.

---

## 2. Команды владельца в Telegram

Только владелец (чей `chat_id` указан в `TG_BOT_OWNER_CHAT_ID`) может выполнять эти команды. Остальным бот ответит, что команда недоступна.

### `/status`

Краткий снимок состояния бота.

**Пример ответа:**
```
Статус: готов
Режим: polling | Логи: plain
Uptime: 3600s
Shutdown: no
Jobs: total=2 search=0 download=2
Limits: u=2 c=4 g=8
Cooldown: user=3s chat=1s burst=5/20s
Executor: thread workers=2 pending=0
Health: on 0.0.0.0:8080
Last monitor: 12:34:56 | Last error: n/a
```

**Когда использовать:** проверить, что бот жив, сколько задач в работе, есть ли запрос на shutdown.

---

### `/jobs`

Список активных задач (поиск и загрузка).

**Пример ответа:**
```
Активных задач: 2
- abc123 download 45s u=167650120 c=167650120 https://soundcloud.com/...
- def456 search 12s u=167650120 c=167650120 artist track
```

**Когда использовать:** понять, кто что качает, не зависла ли задача.

---

### `/restart`

Перезапуск бота. Процесс заменяется новым (`os.execv`), бот поднимается снова в том же процессе.

**Важно:**
- Между командами `/restart` действует cooldown (`RESTART_COOLDOWN_SECONDS`, по умолчанию 30 сек).
- Если есть активные задачи, бот ждёт до `SHUTDOWN_GRACE_SECONDS` (по умолчанию 10 сек), затем перезапускается.
- В ephemeral cloud состояние (настройки, кеш) теряется при перезапуске — это ожидаемо.

**Когда использовать:** после смены кода, при «зависании», после обновления `.env.cloud`.

---

### `/persistence_info`

Информация о файле persistence и временных ключах.

**Пример ответа:**
```
Persistence info:
- Storage path: /tmp/scdlbot.pickle
- Storage exists: yes
- Storage size: 45.2 KiB
- Storage mode: ephemeral (/tmp)
- Version: 1
- Temp search choices: total=2 expired=0
- Temp callback metadata: total=5 expired=0
- Startup hygiene: ok removed=3
```

**Когда использовать:** проверить, не разросся ли persistence, сколько временных ключей.

---

### `/cleanup_persistence`

Ручная очистка просроченных временных ключей (search_choice, callback metadata). Постоянные настройки чатов не трогаются.

**Пример ответа:**
```
Cleanup persistence завершён.
Удалено временных ключей: 12
- search_choice: 3
- callback metadata: 9
Изменено чатов: 2
```

**Когда использовать:** если persistence сильно растёт или после большого потока запросов.

---

## 3. Общедоступные команды (для всех пользователей)

| Команда | Назначение |
|---------|------------|
| `/start` | Приветствие и клавиатура |
| `/help` | Справка по возможностям |
| `/settings` | Настройки (режим dl/link/ask, подписи, неизвестные сайты) |
| `/search <исполнитель> <трек>` | Поиск по площадкам |
| `/dl <ссылка>` | Скачать и прислать файл |
| `/link <ссылка>` | Показать ссылки без загрузки |

---

## 4. Правила эксплуатации

### Один инстанс на токен

- На один `TG_BOT_TOKEN` — только один активный процесс с polling.
- Если запустить второй `make cloud_run` — возможны конфликты и «Address already in use».
- Перед повторным запуском заверши предыдущий процесс (`Ctrl+C` или `pkill -f scdlbot`).

### Порты

- **8080** — healthcheck (`/healthz`, `/readyz`)
- **8000** — Prometheus metrics
- **5000** — используется при webhook (сейчас не задействован)

Если порт занят — бот падает при старте. Убедись, что старый экземпляр остановлен.

### Ephemeral storage (`/tmp`)

- `CHAT_STORAGE` и `DL_DIR` в `/tmp` — данные теряются при перезагрузке VM или остановке процесса.
- Настройки пользователей, кеш поиска — не сохраняются.
- Это нормально для dev/тестовых сценариев.

---

## 5. Переменные окружения для тонкой настройки

### Лимиты и защита от флуда

| Переменная | По умолчанию | Смысл |
|------------|--------------|-------|
| `MAX_ACTIVE_JOBS_PER_USER` | 2 | Макс. активных задач на пользователя |
| `MAX_ACTIVE_JOBS_PER_CHAT` | 4 | Макс. активных задач в чате |
| `MAX_GLOBAL_ACTIVE_JOBS` | 8 | Макс. активных задач всего |
| `USER_REQUEST_COOLDOWN_SECONDS` | 3 | Пауза между запросами от одного пользователя |
| `CHAT_REQUEST_COOLDOWN_SECONDS` | 1 | Пауза между запросами в чате |
| `BURST_REQUEST_LIMIT` | 5 | Макс. запросов в окне burst |
| `BURST_WINDOW_SECONDS` | 20 | Окно для burst (секунды) |

Если много отказов из-за cooldown — можно немного ослабить (осторожно).

### Перезапуск и завершение

| Переменная | По умолчанию | Смысл |
|------------|--------------|-------|
| `RESTART_COOLDOWN_SECONDS` | 30 | Минимальный интервал между `/restart` |
| `SHUTDOWN_GRACE_SECONDS` | 10 | Время ожидания завершения задач перед restart/shutdown |

---

## 6. Проверки и мониторинг

### Health

```bash
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz
```

Ожидается ответ `OK` или аналогичный.

### Логи

- При запуске в терминале — логи идут в stdout.
- При Docker: `docker logs -f <container>`
- При systemd: `journalctl -u scdlbot -f`

### Типичные сообщения в логах

- `Application started` — бот успешно запущен
- `received command: start chat_id=...` — кто-то нажал Start
- `stage=request_rejected ... status=cooldown` — сработал cooldown
- `stage=download_job_scheduled` — задача поставлена в очередь

---

## 7. Что делать при проблемах

| Ситуация | Действие |
|----------|----------|
| Бот не отвечает | Проверить `/status`; при отсутствии ответа — перезапуск через `make cloud_run` |
| Ошибка «Address already in use» | Остановить старый процесс: `pkill -f "python -m scdlbot"` |
| Много отказов по cooldown | Поднять `USER_REQUEST_COOLDOWN_SECONDS` или `BURST_REQUEST_LIMIT` (осторожно) |
| Очередь перегружена | Поднять `MAX_GLOBAL_ACTIVE_JOBS` или `WORKERS` |
| Persistence вырос | Выполнить `/cleanup_persistence` |
| Токен неверный | Новый токен в @BotFather, обновить `TG_BOT_TOKEN` в `.env.cloud` |

---

## 8. Последовательность команд для полного цикла

```
# Первый раз (подготовка)
cp .env.cloud.ready .env.cloud
# Заполнить TG_BOT_TOKEN, TG_BOT_OWNER_CHAT_ID в .env.cloud
bash ./cloud_startup.sh
make cloud_preflight
make cloud_dry_run

# Запуск
make cloud_run

# В Telegram: /start, /status, отправить ссылку на трек

# Остановка (если нужно)
# Ctrl+C в терминале или:
pkill -f "python -m scdlbot"
```

---

## 9. Итог

- **Проект готов к работе** в текущей конфигурации (ephemeral, polling).
- **Команды владельца** — `/status`, `/jobs`, `/restart`, `/persistence_info`, `/cleanup_persistence`.
- **Главное правило** — один экземпляр на один токен, перед новым запуском останавливать предыдущий.
- **Доп. правки** — только при переходе на prod (webhook, persistent storage, новый токен).
