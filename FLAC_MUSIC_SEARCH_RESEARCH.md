# Исследование: Поиск музыки в максимальном качестве и FLAC

## Обзор источников

### 1. Официальные API (метаданные)

| Сервис | FLAC | Качество | Требования | Примечания |
|--------|------|----------|------------|------------|
| **Spotify API** | ❌ | Метаданные только | Бесплатный аккаунт | Отличный поиск, но без аудио |
| **Tidal API** | ✅ | FLAC 16-bit, MQA 24-bit | Premium подписка | Официальный Developer Portal |
| **Qobuz** | ✅ | До 24-bit/192 kHz | Подписка | Лучшее качество на рынке |
| **Deezer API** | ⚠️ | FLAC (нестабильно) | Подписка | Может возвращать MP3 вместо FLAC |
| **MusicBrainz** | ❌ | Метаданные | Бесплатно | Открытая база, связка с AcoustID |

### 2. Инструменты для загрузки FLAC

| Инструмент | Источники | FLAC | Язык | Особенности |
|------------|-----------|------|------|-------------|
| **Streamrip** | Qobuz, Tidal, Deezer, SoundCloud | ✅ | Python | YAML конфиг, batch, до 24/192 |
| **flacfetch** | Spotify→librespot, торренты, YouTube | ✅ | Python | CD-quality, приоритет Official |
| **SpotiFLAC / SpotiFLAC-CLI** | Spotify → Tidal/Qobuz/Amazon | ✅ | - | Без аккаунтов источников |
| **tidal-dl-ng** | Tidal | ✅ | - | HiRes до 24/192 (TIDAL MAX) |
| **GoDeez** | Deezer | ✅ | Go | Плейлисты и альбомы |
| **yt-dlp** | 1000+ сайтов | ⚠️ | Python | Лучший аудио, но редко FLAC |

### 3. Многоплатформенные решения

- **Musicfetch API** — поиск ссылок на 30+ платформ по URL или ISRC (Spotify, Tidal, Qobuz, Amazon и др.)
- **AcoustID + MusicBrainz** — идентификация по отпечатку аудио (Chromaprint)

### 4. Сайты с нативным FLAC

- **Bandcamp** — многие артисты выкладывают FLAC
- **Qobuz Store** — покупка в FLAC
- **HDtracks, ProStudioMasters** — Hi-Res магазины
- **Private trackers** (RED, OPS) — lossless торренты (требуют инвайт)

---

## Рекомендуемая архитектура бота

### Вариант A: Поиск + метаданные (без загрузки)
1. **Spotify API** — поиск по названию/артисту
2. **MusicBrainz** — расширенные метаданные, ISRC
3. **Musicfetch** — ссылки на стриминги

### Вариант B: Поиск + загрузка FLAC
1. **Spotify API** — поиск
2. **Streamrip** или **flacfetch** — загрузка (требуют аккаунты Tidal/Qobuz/Deezer)
3. **yt-dlp** — fallback для YouTube/Bandcamp (best audio)

### Вариант C: Только ссылки
1. Поиск через Spotify/MusicBrainz
2. Возврат ссылок на Tidal, Qobuz, Deezer, Bandcamp
3. Пользователь скачивает сам

---

## Ограничения Telegram

- **Лимит файла**: 50 MB (официальный API), до 2 GB (локальный Bot API)
- **FLAC файл** ~30–50 MB для 5-минутного трека (16/44.1)
- **Решения**: конвертация в 320kbps MP3 для отправки или только ссылки

---

## Необходимые API ключи

| Сервис | Где получить |
|--------|--------------|
| Spotify | https://developer.spotify.com/dashboard |
| Musicfetch | https://musicfetch.io |
| AcoustID | https://acoustid.org/new-application |
| Tidal | https://developer.tidal.com |
| Deezer | https://developers.deezer.com |
