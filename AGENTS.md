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
| Install dependencies | `poetry install --with main,dev,docs` |
| Lint + package checks | `make test` |
| Format code | `make format` |
| Run bot (dev) | `make run_dev` (reads `.env-dev`) |
| Run bot (manual) | `TG_BOT_TOKEN=<token> poetry run python -m scdlbot` |

### Caveats

- `TG_BOT_TOKEN` env var is **required** at module import time (`os.environ["TG_BOT_TOKEN"]`), so even importing the module will fail without it.
- The `make test` target runs `lint` (currently no-op / commented out) and `package` (`poetry check`, `pip check`, `safety check`). There are no unit tests.
- `poetry lock` may be needed if `pyproject.toml` has changed since the lock file was last generated. The update script handles this.
- The `lint` Makefile target is effectively a no-op (linters are commented out). Formatting is done via `make format` (isort + black).
- `poetry` is installed to `~/.local/bin` — ensure `PATH` includes it.
