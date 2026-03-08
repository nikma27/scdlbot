# AGENTS.md

## Cursor Cloud specific instructions

### Overview

**scdlbot** is a single-process Python Telegram bot for downloading music/video from SoundCloud, Bandcamp, YouTube, and many more sites. There is no database, no frontend, and no microservices.

### Tech stack

- Python 3.11+ with Poetry for dependency management
- `python-telegram-bot` 22.x (async)
- External CLI tools: `scdl`, `bandcamp-dl`, `yt-dlp` (all installed as Python dependencies)
- FFmpeg (system dependency, pre-installed on the VM)

### Key commands

| Task | Command |
|---|---|
| Bootstrap cloud env | `bash ./cloud_startup.sh` |
| Create cloud env file | `cp .env.cloud.sample .env.cloud` |
| Cloud preflight checks | `make cloud_preflight` |
| Cloud dry run (no polling/webhook) | `make cloud_dry_run` |
| Cloud bot run | `make cloud_run` |
| Install dependencies | `poetry install --with main,dev,docs,flacbot --sync` |
| Verify FFmpeg | `ffmpeg -version` |
| Lint + package checks | `make test` |
| Fast checks for inner loop | `make test_fast` |
| Format code | `make format` |
| Run bot (dev) | `make run_dev` (reads `.env-dev`) |
| Run bot (manual) | `TG_BOT_TOKEN=<token> poetry run python -m scdlbot` |

### Caveats

- `TG_BOT_TOKEN` env var is **required** at module import time (`os.environ["TG_BOT_TOKEN"]`), so even importing the module will fail without it.
- Cloud sessions should use `.env.cloud` (copied from `.env.cloud.sample`) and not commit secret values.
- The `make test` target runs `lint` (currently no-op / commented out) and `package` (`poetry check`, `pip check`, `safety check`). There are no unit tests.
- `make test_fast` is intended for quick feedback in cloud sessions; it skips `poetry check` and vulnerability scan, so run full `make test` before shipping changes.
- `poetry lock` may be needed if `pyproject.toml` has changed since the lock file was last generated. The update script handles this.
- The `lint` Makefile target is effectively a no-op (linters are commented out). Formatting is done via `make format` (isort + black).
- `poetry` is installed to `~/.local/bin`; startup scripts should always export `PATH="$HOME/.local/bin:$PATH"` before running Poetry commands.
- For production-like cloud verification without long-running process, use `make cloud_dry_run` with `CLOUD_DRY_RUN=1`.
- Quality fallback can be tuned with `QUALITY_MIN_BITRATE_KBPS`, `PREFER_LOSSLESS`, `ENABLE_CROSS_PLATFORM_SEARCH`, `ENABLE_WEB_FALLBACK`, and `YOUTUBE_MIN_HEIGHT`.

### Recommended cloud startup script

Use and keep `cloud_startup.sh` as the default startup routine in Cursor Cloud:

1. Export `~/.local/bin` in `PATH`
2. Ensure Poetry is installed (install via `python3 -m pip install --user poetry` when missing)
3. Verify FFmpeg is available in `PATH`
4. Run `poetry install --with main,dev,docs,flacbot --sync`
5. Copy `.env.cloud.sample` to `.env.cloud`, fill real secrets, and run `make cloud_preflight`

For operator-facing sequence, use `CLOUD_SETUP.md`.

### make test optimization ideas

- Use `make test_fast` during edit/debug loops and run full `make test` only before commit.
- Replace deprecated `safety check` with `safety scan` in a dedicated follow-up to avoid future CLI breakage.
- Keep `poetry.lock` in sync to avoid expensive retry cycles when `poetry check` fails early.
