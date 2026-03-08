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

## 3) Run bot in cloud session

1. `make cloud_run`

`BOT_MODE=scdlbot` runs downloader bot, `BOT_MODE=flacbot` runs search bot.

## 4) Fast development loop

1. `make test_fast` during edits
2. `make test` before commit/push

## 5) Deployment notes

- Keep major dependency upgrades (`scdl`, `doc8`) in separate PRs and validate bot behavior before rollout.
- Keep `.env.cloud` out of git; commit only `.env.cloud.sample`.
- Quality fallback controls for `scdlbot`:
  - `QUALITY_MIN_BITRATE_KBPS` (default `320`)
  - `PREFER_LOSSLESS` (`1` means try to upgrade lossy tracks)
  - `ENABLE_CROSS_PLATFORM_SEARCH` and `ENABLE_WEB_FALLBACK`
  - `FALLBACK_MAX_CANDIDATES` to cap probing cost.
  - `YOUTUBE_MIN_HEIGHT` (default `1080`) for YouTube HD-priority fallback.
