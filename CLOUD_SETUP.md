# Cloud Setup Checklist

Use this checklist to run `scdlbot`/`flacbot` only in cloud environments.

## 1) Bootstrap runtime

Run all commands from repository root (`/workspace` in Cursor Cloud).

1. `bash ./cloud_startup.sh`
2. `cp .env.cloud.sample .env.cloud`
3. Fill secrets in `.env.cloud`:
   - `TG_BOT_TOKEN`
   - `TG_BOT_OWNER_CHAT_ID` (for `scdlbot`)
   - `WEBHOOK_APP_URL_ROOT` if `WEBHOOK_ENABLE=1`
   - optional Spotify creds for `flacbot`

## 2) Validate environment

1. `make cloud_preflight`
2. `make cloud_dry_run`

`cloud_preflight` now checks:
- env/config coherence (Python validator)
- `ffmpeg` availability
- downloader CLI presence (`yt-dlp`, `scdl`, `bandcamp-dl`)
- writable storage paths from config

## 3) Run bot in cloud session

1. `make cloud_run`

`BOT_MODE=scdlbot` runs downloader bot, `BOT_MODE=flacbot` runs search bot.

## 4) Fast development loop

1. `make test_fast` during edits
2. `make smoke_test` for quick Python-level smoke tests
3. `make test` before commit/push

## 5) Deployment notes

- Keep major dependency upgrades (`scdl`, `doc8`) in separate PRs and validate bot behavior before rollout.
- Keep `.env.cloud` out of git; commit only `.env.cloud.sample`.
- Detailed runtime workflow for search/download: `SEARCH_WORKFLOW.md`.
- Operational runbook for health/restart/admission limits: `OPERATIONS.md`.
- Quality fallback controls for `scdlbot`:
  - `QUALITY_MIN_BITRATE_KBPS` (default `320`)
  - `PREFER_LOSSLESS` (`1` means try to upgrade lossy tracks)
  - `ENABLE_CROSS_PLATFORM_SEARCH` and `ENABLE_WEB_FALLBACK`
  - `FALLBACK_MAX_CANDIDATES` to cap probing cost.
  - `YOUTUBE_MIN_HEIGHT` (default `1080`) for YouTube HD-priority fallback.
- Runtime safety controls:
  - `MAX_ACTIVE_JOBS_PER_USER`, `MAX_ACTIVE_JOBS_PER_CHAT`, `MAX_GLOBAL_ACTIVE_JOBS`
  - `USER_REQUEST_COOLDOWN_SECONDS`, `CHAT_REQUEST_COOLDOWN_SECONDS`, `BURST_REQUEST_LIMIT`, `BURST_WINDOW_SECONDS`
  - `TEMP_FILE_TTL_SECONDS`, `DL_DIR_MAX_BYTES`, `DL_DIR_MAX_FILE_COUNT`
