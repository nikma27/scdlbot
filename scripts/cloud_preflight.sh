#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

if ! command -v poetry >/dev/null 2>&1; then
  echo "poetry is missing; run: bash ./cloud_startup.sh (and ensure .env.cloud exists: cp .env.cloud.sample .env.cloud)" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is missing in PATH" >&2
  exit 1
fi

BOT_MODE="${BOT_MODE:-scdlbot}"
if [[ "${BOT_MODE}" != "scdlbot" && "${BOT_MODE}" != "flacbot" ]]; then
  echo "BOT_MODE must be either 'scdlbot' or 'flacbot'" >&2
  exit 1
fi

if [[ -z "${TG_BOT_TOKEN:-}" ]]; then
  echo "TG_BOT_TOKEN is required" >&2
  exit 1
fi

if [[ "${BOT_MODE}" == "scdlbot" && "${WEBHOOK_ENABLE:-0}" == "1" ]]; then
  if [[ -z "${WEBHOOK_APP_URL_ROOT:-}" ]]; then
    echo "WEBHOOK_APP_URL_ROOT is required when WEBHOOK_ENABLE=1" >&2
    exit 1
  fi
fi

echo "Poetry: $(poetry --version)"
echo "FFmpeg: $(ffmpeg -version | sed -n '1p')"
echo "BOT_MODE: ${BOT_MODE}"

# Python-level deterministic config/dependency preflight.
poetry run python -m scdlbot.config_validation --preflight

# Validate key CLI tools are available from Poetry environment.
poetry run python -c "import shutil; req=['scdl','bandcamp-dl','yt-dlp']; missing=[x for x in req if shutil.which(x) is None]; print('Missing CLI tools: ' + ', '.join(missing) if missing else 'All downloader CLI tools are available.'); raise SystemExit(1 if missing else 0)"

if [[ "${BOT_MODE}" == "flacbot" ]]; then
  if [[ -z "${SPOTIFY_CLIENT_ID:-}" || -z "${SPOTIFY_CLIENT_SECRET:-}" ]]; then
    echo "Warning: Spotify creds are not set; flacbot will use fallback providers."
  fi
fi

echo "Cloud preflight checks passed."
