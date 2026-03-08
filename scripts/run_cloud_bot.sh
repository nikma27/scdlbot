#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

BOT_MODE="${BOT_MODE:-scdlbot}"
DRY_RUN="${CLOUD_DRY_RUN:-0}"

if [[ "${BOT_MODE}" == "scdlbot" ]]; then
  if [[ "${DRY_RUN}" == "1" ]]; then
    poetry run python -c "import scdlbot.__main__; print('dry_run_ok:scdlbot')"
    exit 0
  fi
  exec poetry run python -m scdlbot
elif [[ "${BOT_MODE}" == "flacbot" ]]; then
  if [[ "${DRY_RUN}" == "1" ]]; then
    poetry run python -c "import flacbot.__main__; print('dry_run_ok:flacbot')"
    exit 0
  fi
  exec poetry run python -m flacbot
else
  echo "BOT_MODE must be either 'scdlbot' or 'flacbot'" >&2
  exit 1
fi
