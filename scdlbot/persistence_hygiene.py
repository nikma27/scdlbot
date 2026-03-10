"""Helpers for safe PicklePersistence inspection, cleanup and migration."""

from __future__ import annotations

import os
import pickle
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, MutableMapping

PERSISTENCE_VERSION_KEY = "__scdlbot_persistence_version__"
CURRENT_PERSISTENCE_VERSION = 1
SEARCH_CHOICE_CACHE_PREFIX = "search_choice:"


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_mutable_dict(value: Any) -> MutableMapping:
    return value if isinstance(value, MutableMapping) else {}


def _coerce_version(value: Any, *, default: int = 1) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def infer_persistence_version(bot_data: Mapping[str, Any] | None) -> int:
    if not isinstance(bot_data, Mapping):
        return 1
    return _coerce_version(bot_data.get(PERSISTENCE_VERSION_KEY), default=1)


def migrate_persistence_state(raw_state: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize persisted state and ensure version marker for future migrations."""
    normalized = _as_dict(raw_state).copy()
    state_was_dict = isinstance(raw_state, dict)
    bot_data = _as_dict(normalized.get("bot_data")).copy()
    chat_data = _as_dict(normalized.get("chat_data")).copy()
    user_data = _as_dict(normalized.get("user_data")).copy()
    conversations = _as_dict(normalized.get("conversations")).copy()
    callback_data = _as_dict(normalized.get("callback_data")).copy()

    old_version = infer_persistence_version(bot_data)
    bot_data[PERSISTENCE_VERSION_KEY] = CURRENT_PERSISTENCE_VERSION

    normalized["bot_data"] = bot_data
    normalized["chat_data"] = chat_data
    normalized["user_data"] = user_data
    normalized["conversations"] = conversations
    normalized["callback_data"] = callback_data

    summary = {
        "state_was_dict": state_was_dict,
        "old_version": old_version,
        "new_version": CURRENT_PERSISTENCE_VERSION,
        "version_updated": old_version != CURRENT_PERSISTENCE_VERSION,
        "normalized_structure": not state_was_dict
        or not isinstance(raw_state.get("bot_data"), dict)
        or not isinstance(raw_state.get("chat_data"), dict)
        or not isinstance(raw_state.get("user_data"), dict)
        or not isinstance(raw_state.get("conversations"), dict)
        or not isinstance(raw_state.get("callback_data"), dict),
    }
    return normalized, summary


def _is_numeric_key(key: Any) -> bool:
    if isinstance(key, int):
        return True
    if isinstance(key, str):
        return key.isdigit()
    return False


def _is_ephemeral_callback_state(key: Any, value: Any) -> bool:
    if not _is_numeric_key(key):
        return False
    if not isinstance(value, Mapping):
        return False
    if bool(value.get("__ephemeral__")):
        return True
    return "urls" in value


def _is_expired(created_at: Any, *, now_ts: float, ttl_seconds: int) -> bool:
    if ttl_seconds <= 0:
        return True
    if not isinstance(created_at, (int, float)):
        return True
    return (now_ts - float(created_at)) > float(ttl_seconds)


def cleanup_chat_data_ephemeral(
    chat_data: MutableMapping[Any, Any],
    *,
    now_ts: float | None = None,
    search_choice_ttl_seconds: int = 900,
    ephemeral_request_ttl_seconds: int = 3600,
    dry_run: bool = False,
) -> dict[str, int]:
    """Cleanup ephemeral chat_data keys and return counters."""
    now_value = now_ts if now_ts is not None else time.time()
    summary = {
        "search_choice_total": 0,
        "search_choice_expired": 0,
        "search_choice_removed": 0,
        "ephemeral_request_total": 0,
        "ephemeral_request_expired": 0,
        "ephemeral_request_removed": 0,
    }
    for key in list(chat_data.keys()):
        value = chat_data.get(key)
        key_text = str(key)
        if key_text.startswith(SEARCH_CHOICE_CACHE_PREFIX):
            summary["search_choice_total"] += 1
            expired = _is_expired(
                value.get("created_at") if isinstance(value, Mapping) else None,
                now_ts=now_value,
                ttl_seconds=search_choice_ttl_seconds,
            )
            if expired:
                summary["search_choice_expired"] += 1
                if not dry_run:
                    chat_data.pop(key, None)
                    summary["search_choice_removed"] += 1
            continue
        if _is_ephemeral_callback_state(key, value):
            summary["ephemeral_request_total"] += 1
            expired = _is_expired(
                value.get("created_at") if isinstance(value, Mapping) else None,
                now_ts=now_value,
                ttl_seconds=ephemeral_request_ttl_seconds,
            )
            if expired:
                summary["ephemeral_request_expired"] += 1
                if not dry_run:
                    chat_data.pop(key, None)
                    summary["ephemeral_request_removed"] += 1
    return summary


def cleanup_persistence_state(
    state: MutableMapping[str, Any],
    *,
    now_ts: float | None = None,
    search_choice_ttl_seconds: int = 900,
    ephemeral_request_ttl_seconds: int = 3600,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Cleanup ephemeral entries across all chats."""
    now_value = now_ts if now_ts is not None else time.time()
    chat_data = _as_mutable_dict(state.get("chat_data"))
    summary = {
        "chats_total": len(chat_data),
        "chat_entries_not_dict": 0,
        "search_choice_total": 0,
        "search_choice_expired": 0,
        "search_choice_removed": 0,
        "ephemeral_request_total": 0,
        "ephemeral_request_expired": 0,
        "ephemeral_request_removed": 0,
        "chats_changed": 0,
    }
    for chat_id, chat_state in chat_data.items():
        if not isinstance(chat_state, MutableMapping):
            summary["chat_entries_not_dict"] += 1
            continue
        before_size = len(chat_state)
        chat_summary = cleanup_chat_data_ephemeral(
            chat_state,
            now_ts=now_value,
            search_choice_ttl_seconds=search_choice_ttl_seconds,
            ephemeral_request_ttl_seconds=ephemeral_request_ttl_seconds,
            dry_run=dry_run,
        )
        for key in (
            "search_choice_total",
            "search_choice_expired",
            "search_choice_removed",
            "ephemeral_request_total",
            "ephemeral_request_expired",
            "ephemeral_request_removed",
        ):
            summary[key] += chat_summary[key]
        if not dry_run and len(chat_state) != before_size:
            summary["chats_changed"] += 1
    return summary


def inspect_persistence_state(
    state: Mapping[str, Any] | None,
    *,
    now_ts: float | None = None,
    search_choice_ttl_seconds: int = 900,
    ephemeral_request_ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Read-only inspection summary for persisted state."""
    normalized, migration_summary = migrate_persistence_state(state or {})
    cleanup_summary = cleanup_persistence_state(
        normalized,
        now_ts=now_ts,
        search_choice_ttl_seconds=search_choice_ttl_seconds,
        ephemeral_request_ttl_seconds=ephemeral_request_ttl_seconds,
        dry_run=True,
    )
    return {
        "version": migration_summary["new_version"],
        "old_version": migration_summary["old_version"],
        "chats_total": cleanup_summary["chats_total"],
        "users_total": len(_as_dict(normalized.get("user_data"))),
        "search_choice_total": cleanup_summary["search_choice_total"],
        "search_choice_expired": cleanup_summary["search_choice_expired"],
        "ephemeral_request_total": cleanup_summary["ephemeral_request_total"],
        "ephemeral_request_expired": cleanup_summary["ephemeral_request_expired"],
        "chat_entries_not_dict": cleanup_summary["chat_entries_not_dict"],
    }


def get_storage_file_info(storage_path: str) -> dict[str, Any]:
    path = Path(storage_path).expanduser()
    info = {"exists": path.exists(), "size_bytes": 0, "mtime": 0.0, "path": str(path)}
    if not path.exists():
        return info
    stat = path.stat()
    info["size_bytes"] = int(stat.st_size)
    info["mtime"] = float(stat.st_mtime)
    return info


def load_pickle_state(storage_path: str) -> Any:
    with open(storage_path, "rb") as handle:
        return pickle.load(handle)


def atomic_write_pickle_state(storage_path: str, state: Mapping[str, Any]) -> None:
    target_path = Path(storage_path).expanduser()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=str(target_path.parent), delete=False) as tmp_file:
        pickle.dump(dict(state), tmp_file, protocol=pickle.HIGHEST_PROTOCOL)
        tmp_name = tmp_file.name
    os.replace(tmp_name, str(target_path))


def backup_persistence_file(storage_path: str, *, suffix: str, now_ts: float | None = None) -> str:
    path = Path(storage_path).expanduser()
    timestamp = int(now_ts if now_ts is not None else time.time())
    backup_path = path.with_name(f"{path.name}.{suffix}.{timestamp}.bak")
    shutil.move(str(path), str(backup_path))
    return str(backup_path)


def prepare_persistence_file(
    storage_path: str,
    *,
    now_ts: float | None = None,
    search_choice_ttl_seconds: int = 900,
    ephemeral_request_ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Load, migrate and cleanup persistence file before bot startup."""
    summary: dict[str, Any] = {
        "path": str(Path(storage_path).expanduser()),
        "status": "noop",
        "loaded": False,
        "kept": 0,
        "removed": 0,
        "backup_path": "",
        "error": "",
        "version_before": 1,
        "version_after": CURRENT_PERSISTENCE_VERSION,
    }
    file_info = get_storage_file_info(storage_path)
    summary["exists"] = file_info["exists"]
    summary["size_bytes"] = file_info["size_bytes"]
    if not file_info["exists"]:
        summary["status"] = "not_found"
        return summary

    try:
        loaded_state = load_pickle_state(storage_path)
        summary["loaded"] = True
    except Exception as exc:
        summary["status"] = "corrupt_backup_created"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        try:
            summary["backup_path"] = backup_persistence_file(storage_path, suffix="corrupt", now_ts=now_ts)
        except Exception as backup_exc:
            summary["status"] = "corrupt_backup_failed"
            summary["error"] += f" | backup_failed: {type(backup_exc).__name__}: {backup_exc}"
        return summary

    normalized_state, migration_summary = migrate_persistence_state(loaded_state)
    cleanup_summary = cleanup_persistence_state(
        normalized_state,
        now_ts=now_ts,
        search_choice_ttl_seconds=search_choice_ttl_seconds,
        ephemeral_request_ttl_seconds=ephemeral_request_ttl_seconds,
        dry_run=False,
    )
    summary["version_before"] = migration_summary["old_version"]
    summary["version_after"] = migration_summary["new_version"]
    summary["removed"] = int(cleanup_summary["search_choice_removed"] + cleanup_summary["ephemeral_request_removed"])
    summary["kept"] = int(
        cleanup_summary["search_choice_total"]
        - cleanup_summary["search_choice_removed"]
        + cleanup_summary["ephemeral_request_total"]
        - cleanup_summary["ephemeral_request_removed"]
    )
    summary["search_choice_removed"] = cleanup_summary["search_choice_removed"]
    summary["ephemeral_request_removed"] = cleanup_summary["ephemeral_request_removed"]
    changed = bool(
        summary["removed"]
        or migration_summary["version_updated"]
        or migration_summary["normalized_structure"]
    )
    if not changed:
        summary["status"] = "loaded_no_changes"
        return summary

    try:
        summary["backup_path"] = backup_persistence_file(storage_path, suffix="preclean", now_ts=now_ts)
        atomic_write_pickle_state(storage_path, normalized_state)
        summary["status"] = "cleaned_and_saved"
    except Exception as exc:
        summary["status"] = "cleaned_save_failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        # If we moved original to backup and failed writing new file, restore backup.
        backup_path = summary.get("backup_path") or ""
        if backup_path:
            try:
                shutil.move(backup_path, storage_path)
                summary["status"] = "restore_after_save_failed"
            except Exception as restore_exc:
                summary["error"] += f" | restore_failed: {type(restore_exc).__name__}: {restore_exc}"
    return summary
