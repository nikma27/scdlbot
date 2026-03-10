#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

if ! command -v poetry >/dev/null 2>&1; then
  python3 -m pip install --user poetry
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is not available in PATH" >&2
  exit 1
fi

echo "Poetry: $(poetry --version)"
echo "FFmpeg: $(ffmpeg -version | sed -n '1p')"

# Install all groups used by scdlbot + flacbot development/testing.
poetry install --with main,dev,docs,flacbot --sync
