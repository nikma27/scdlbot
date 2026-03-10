"""Runtime configuration validation and redaction helpers."""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


SENSITIVE_KEY_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "AUTH", "COOKIE", "KEY")
SUPPORTED_EXECUTOR_KINDS = {"thread", "process"}
SUPPORTED_BOT_MODES = {"scdlbot", "flacbot"}

INT_ENV_KEYS = (
    "TG_BOT_OWNER_CHAT_ID",
    "WORKERS",
    "DL_TIMEOUT",
    "CHECK_URL_TIMEOUT",
    "COMMON_CONNECTION_TIMEOUT",
    "MAX_TG_FILE_SIZE",
    "MAX_CONVERT_FILE_SIZE",
    "QUALITY_MIN_BITRATE_KBPS",
    "FALLBACK_MAX_CANDIDATES",
    "YOUTUBE_MIN_HEIGHT",
    "SEARCH_RESULT_LIMIT",
    "PORT",
    "METRICS_PORT",
    "HEALTHCHECK_PORT",
    "TEMP_FILE_TTL_SECONDS",
    "DL_DIR_MAX_BYTES",
    "DL_DIR_MAX_FILE_COUNT",
    "SEARCH_CHOICE_TTL_SECONDS",
    "PERSISTENCE_EPHEMERAL_TTL_SECONDS",
    "RESTART_COOLDOWN_SECONDS",
    "SHUTDOWN_GRACE_SECONDS",
    "MAX_ACTIVE_JOBS_PER_USER",
    "MAX_ACTIVE_JOBS_PER_CHAT",
    "MAX_GLOBAL_ACTIVE_JOBS",
    "USER_REQUEST_COOLDOWN_SECONDS",
    "CHAT_REQUEST_COOLDOWN_SECONDS",
    "BURST_REQUEST_LIMIT",
    "BURST_WINDOW_SECONDS",
)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _safe_url_preview(value: str) -> str:
    try:
        parsed = urlparse(value)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"[:180]
    except Exception:
        return value[:180]


def redact_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    key_upper = (key or "").upper()
    value_str = str(value)
    if any(marker in key_upper for marker in SENSITIVE_KEY_MARKERS):
        return "[redacted]"
    if value_str.startswith("http://") or value_str.startswith("https://"):
        return _safe_url_preview(value_str)
    if len(value_str) > 200:
        return value_str[:200] + "..."
    return value


def sanitize_mapping_for_log(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in values.items()}


def _is_int(value: str) -> bool:
    try:
        int(str(value).replace("_", ""))
        return True
    except Exception:
        return False


def _check_writable_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def validate_runtime_config(parsed: Mapping[str, Any], env: Mapping[str, str] | None = None) -> ValidationResult:
    env_map = env or os.environ
    result = ValidationResult()

    token = (parsed.get("TG_BOT_TOKEN") or "").strip()
    if not token:
        result.errors.append("TG_BOT_TOKEN is required and cannot be empty.")

    for key in INT_ENV_KEYS:
        raw = env_map.get(key)
        if raw is None or raw == "":
            continue
        if not _is_int(raw):
            result.errors.append(f"{key} must be an integer value.")

    owner_raw = (env_map.get("TG_BOT_OWNER_CHAT_ID") or "").strip()
    if owner_raw and _is_int(owner_raw):
        owner_value = int(owner_raw.replace("_", ""))
        if owner_value < 0:
            result.errors.append("TG_BOT_OWNER_CHAT_ID cannot be negative.")

    workers = int(parsed.get("WORKERS", 0) or 0)
    if workers <= 0:
        result.errors.append("WORKERS must be a positive integer.")
    elif workers > 16:
        result.warnings.append("WORKERS is high; verify CPU/RAM headroom.")

    executor_kind = str(parsed.get("EXECUTOR_KIND", "")).lower()
    if executor_kind not in SUPPORTED_EXECUTOR_KINDS:
        result.errors.append("EXECUTOR_KIND must be one of: thread, process.")

    for timeout_key in ("DL_TIMEOUT", "CHECK_URL_TIMEOUT", "COMMON_CONNECTION_TIMEOUT"):
        timeout_value = int(parsed.get(timeout_key, 0) or 0)
        if timeout_value <= 0:
            result.errors.append(f"{timeout_key} must be > 0.")

    for port_key in ("METRICS_PORT", "HEALTHCHECK_PORT", "WEBHOOK_PORT"):
        if port_key == "HEALTHCHECK_PORT" and not bool(parsed.get("HEALTHCHECK_ENABLE")):
            continue
        if port_key == "WEBHOOK_PORT" and not bool(parsed.get("WEBHOOK_ENABLE")):
            continue
        value = int(parsed.get(port_key, 0) or 0)
        if value < 1 or value > 65535:
            result.errors.append(f"{port_key} must be in range 1..65535.")

    chat_storage_path = Path(str(parsed.get("CHAT_STORAGE", "/tmp/scdlbot.pickle"))).expanduser()
    chat_storage_parent = chat_storage_path.parent
    chat_storage_fallback_path = Path(str(parsed.get("CHAT_STORAGE_FALLBACK", "/tmp/scdlbot.pickle"))).expanduser()
    chat_storage_fallback_parent = chat_storage_fallback_path.parent
    if not _check_writable_directory(chat_storage_parent):
        if _check_writable_directory(chat_storage_fallback_parent):
            result.warnings.append(
                f"CHAT_STORAGE parent is not writable: {chat_storage_parent}; runtime will fallback to {chat_storage_fallback_path}"
            )
        else:
            result.errors.append(
                f"CHAT_STORAGE parent is not writable: {chat_storage_parent} and fallback is not writable: {chat_storage_fallback_parent}"
            )

    dl_dir = Path(str(parsed.get("DL_DIR", "/tmp/scdlbot"))).expanduser()
    dl_dir_fallback = Path(str(parsed.get("DL_DIR_FALLBACK", "/tmp/scdlbot"))).expanduser()
    if not _check_writable_directory(dl_dir):
        if _check_writable_directory(dl_dir_fallback):
            result.warnings.append(f"DL_DIR is not writable: {dl_dir}; runtime will fallback to {dl_dir_fallback}")
        else:
            result.errors.append(f"DL_DIR is not writable: {dl_dir} and fallback is not writable: {dl_dir_fallback}")

    cookies_file = (parsed.get("COOKIES_FILE") or "").strip()
    if cookies_file and not cookies_file.startswith("http") and not cookies_file.startswith("firefox:"):
        cookie_path = Path(cookies_file).expanduser()
        if not cookie_path.exists():
            result.warnings.append(f"COOKIES_FILE path does not exist: {cookie_path}")
        elif not os.access(cookie_path, os.R_OK):
            result.warnings.append(f"COOKIES_FILE path is not readable: {cookie_path}")

    bot_mode = (env_map.get("BOT_MODE") or "").strip().lower()
    if bot_mode and bot_mode not in SUPPORTED_BOT_MODES:
        result.errors.append("BOT_MODE must be either scdlbot or flacbot.")

    webhook_enabled = bool(parsed.get("WEBHOOK_ENABLE"))
    if webhook_enabled:
        if not (parsed.get("WEBHOOK_APP_URL_ROOT") or "").strip():
            result.errors.append("WEBHOOK_APP_URL_ROOT is required when WEBHOOK_ENABLE=1.")
        if not (parsed.get("WEBHOOK_APP_URL_PATH") or "").strip():
            result.warnings.append("WEBHOOK_APP_URL_PATH is empty while webhook mode is enabled.")

    if bool(parsed.get("TG_BOT_API_LOCAL_MODE")) and "127.0.0.1" not in str(parsed.get("TG_BOT_API", "")) and "localhost" not in str(parsed.get("TG_BOT_API", "")):
        result.warnings.append("TG_BOT_API_LOCAL_MODE=1 but TG_BOT_API does not look local.")

    if int(parsed.get("MAX_GLOBAL_ACTIVE_JOBS", 0) or 0) > 0 and int(parsed.get("MAX_ACTIVE_JOBS_PER_CHAT", 0) or 0) > int(parsed.get("MAX_GLOBAL_ACTIVE_JOBS", 0) or 0):
        result.warnings.append("MAX_ACTIVE_JOBS_PER_CHAT is greater than MAX_GLOBAL_ACTIVE_JOBS.")

    result.infos.append("Runtime configuration validation completed.")
    return result


def run_preflight_checks(parsed: Mapping[str, Any], env: Mapping[str, str] | None = None) -> ValidationResult:
    env_map = env or os.environ
    result = validate_runtime_config(parsed, env_map)

    if shutil.which("ffmpeg") is None:
        result.errors.append("ffmpeg is not available in PATH.")

    try:
        importlib.import_module("yt_dlp")
    except Exception:
        result.warnings.append("yt_dlp import failed. Ensure Poetry dependencies are installed.")

    for cli_name in ("yt-dlp", "scdl", "bandcamp-dl"):
        if shutil.which(cli_name) is None:
            result.warnings.append(f"CLI tool is not in PATH: {cli_name}")

    return result


def _default_parsed_from_env(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    env_map = env or os.environ

    def _int(name: str, default: int) -> int:
        raw = (env_map.get(name) or "").strip()
        if not raw:
            return default
        try:
            return int(raw.replace("_", ""))
        except Exception:
            return default

    def _bool(name: str, default: bool) -> bool:
        raw = (env_map.get(name) or "").strip()
        if not raw:
            return default
        return raw in {"1", "true", "True", "yes", "on"}

    token = (env_map.get("TG_BOT_TOKEN") or "").strip()
    tg_api = env_map.get("TG_BOT_API", "https://api.telegram.org")
    tg_local = _bool("TG_BOT_API_LOCAL_MODE", False) or ("127.0.0.1" in tg_api or "localhost" in tg_api)

    return {
        "TG_BOT_TOKEN": token,
        "TG_BOT_API": tg_api,
        "TG_BOT_API_LOCAL_MODE": tg_local,
        "CHAT_STORAGE": env_map.get("CHAT_STORAGE", "/tmp/scdlbot.pickle"),
        "CHAT_STORAGE_FALLBACK": env_map.get("CHAT_STORAGE_FALLBACK", "/tmp/scdlbot.pickle"),
        "DL_DIR": env_map.get("DL_DIR", "/tmp/scdlbot"),
        "DL_DIR_FALLBACK": env_map.get("DL_DIR_FALLBACK", "/tmp/scdlbot"),
        "WORKERS": _int("WORKERS", 2),
        "EXECUTOR_KIND": env_map.get("EXECUTOR_KIND", "thread"),
        "DL_TIMEOUT": _int("DL_TIMEOUT", 300),
        "CHECK_URL_TIMEOUT": _int("CHECK_URL_TIMEOUT", 30),
        "COMMON_CONNECTION_TIMEOUT": _int("COMMON_CONNECTION_TIMEOUT", 10),
        "METRICS_PORT": _int("METRICS_PORT", 8000),
        "HEALTHCHECK_ENABLE": _bool("HEALTHCHECK_ENABLE", False),
        "HEALTHCHECK_PORT": _int("HEALTHCHECK_PORT", 8080),
        "PERSISTENCE_EPHEMERAL_TTL_SECONDS": _int("PERSISTENCE_EPHEMERAL_TTL_SECONDS", 3600),
        "WEBHOOK_ENABLE": _bool("WEBHOOK_ENABLE", False),
        "WEBHOOK_APP_URL_ROOT": env_map.get("WEBHOOK_APP_URL_ROOT", ""),
        "WEBHOOK_APP_URL_PATH": env_map.get("WEBHOOK_APP_URL_PATH", ""),
        "WEBHOOK_PORT": _int("PORT", 5000),
        "COOKIES_FILE": env_map.get("COOKIES_FILE", ""),
        "MAX_ACTIVE_JOBS_PER_CHAT": _int("MAX_ACTIVE_JOBS_PER_CHAT", 4),
        "MAX_GLOBAL_ACTIVE_JOBS": _int("MAX_GLOBAL_ACTIVE_JOBS", 8),
    }


def _print_validation(result: ValidationResult) -> None:
    for info in result.infos:
        print(f"[INFO] {info}")
    for warning in result.warnings:
        print(f"[WARN] {warning}")
    for error in result.errors:
        print(f"[ERROR] {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate scdlbot runtime configuration")
    parser.add_argument("--preflight", action="store_true", help="Run extended preflight checks")
    args = parser.parse_args()

    parsed = _default_parsed_from_env()
    result = run_preflight_checks(parsed) if args.preflight else validate_runtime_config(parsed)
    _print_validation(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
