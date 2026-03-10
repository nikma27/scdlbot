"""Runtime and observability helpers for long-running bot process."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


def safe_url_preview(url: str | None, *, max_len: int = 180) -> str:
    """Return URL preview without query/fragment to avoid leaks."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        preview = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        preview = str(url)
    return preview[:max_len]


def utc_iso(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc)
    return dt.isoformat()


@dataclass
class RuntimeState:
    """Small thread-safe runtime state for health/ops visibility."""

    started_at: float = field(default_factory=time.time)
    ready: bool = False
    last_monitor_tick: float = 0.0
    last_error_ts: float = 0.0
    last_successful_request_ts: float = 0.0
    last_restart_request_ts: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set_ready(self, value: bool = True) -> None:
        with self._lock:
            self.ready = value

    def mark_monitor_tick(self) -> None:
        with self._lock:
            self.last_monitor_tick = time.time()

    def mark_error(self) -> None:
        with self._lock:
            self.last_error_ts = time.time()

    def mark_success(self) -> None:
        with self._lock:
            self.last_successful_request_ts = time.time()

    def mark_restart_request(self) -> None:
        with self._lock:
            self.last_restart_request_ts = time.time()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            return {
                "started_at": self.started_at,
                "uptime_seconds": max(0, int(now - self.started_at)),
                "ready": self.ready,
                "last_monitor_tick": self.last_monitor_tick,
                "last_error_ts": self.last_error_ts,
                "last_successful_request_ts": self.last_successful_request_ts,
                "last_restart_request_ts": self.last_restart_request_ts,
            }


class JsonLogFormatter(logging.Formatter):
    """Emit compact JSON log lines for machine parsing."""

    KNOWN_FIELDS = (
        "event",
        "chat_id",
        "user_id",
        "request_type",
        "query_preview",
        "url_preview",
        "source",
        "status",
    )

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting utility
        payload: dict[str, Any] = {
            "ts": utc_iso(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in self.KNOWN_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            exc_type = record.exc_info[0]
            exc_val = record.exc_info[1]
            payload["exception_type"] = exc_type.__name__ if exc_type else "Exception"
            payload["exception_message"] = str(exc_val) if exc_val else ""
        return json.dumps(payload, ensure_ascii=False)


def get_executor_pending_count(executor: Any) -> int:
    """Best-effort pending task count without crashing on backend differences."""
    pending = getattr(executor, "_pending_work_items", None)
    if isinstance(pending, dict):
        return len(pending)
    pending = getattr(executor, "_pending_tasks", None)
    if isinstance(pending, (dict, list, set, tuple)):
        return len(pending)
    queue_obj = getattr(executor, "_task_queue", None)
    if queue_obj and hasattr(queue_obj, "qsize"):
        try:
            return int(queue_obj.qsize())
        except Exception:
            return 0
    return 0


def summarize_executor(executor: Any) -> dict[str, Any]:
    return {
        "executor_class": executor.__class__.__name__,
        "pending_tasks": get_executor_pending_count(executor),
    }


def _entry_stats(path: Path) -> tuple[int, int]:
    if path.is_file():
        try:
            return path.stat().st_size, 1
        except Exception:
            return 0, 0
    total_size = 0
    total_files = 0
    for root, _, files in os.walk(path):
        for file_name in files:
            file_path = Path(root) / file_name
            try:
                total_size += file_path.stat().st_size
                total_files += 1
            except Exception:
                continue
    return total_size, total_files


def _safe_delete_entry(base_dir: Path, entry_path: Path) -> bool:
    try:
        base_real = str(base_dir.resolve())
        entry_real = str(entry_path.resolve())
    except Exception:
        return False
    if not entry_real.startswith(base_real + os.sep) and entry_real != base_real:
        return False
    if entry_path.is_dir():
        shutil.rmtree(entry_path, ignore_errors=True)
        return True
    try:
        entry_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def cleanup_dl_dir(
    dl_dir: str,
    *,
    ttl_seconds: int,
    max_total_bytes: int,
    max_file_count: int,
    logger: logging.Logger,
) -> dict[str, int]:
    """Best-effort cleanup for download temp directory."""
    stats = {"removed_entries": 0, "removed_bytes": 0, "removed_files": 0}
    base_dir = Path(dl_dir)
    if not base_dir.exists() or not base_dir.is_dir():
        return stats
    now = time.time()
    entries = []
    for entry in base_dir.iterdir():
        try:
            mtime = entry.stat().st_mtime
        except Exception:
            continue
        size_bytes, file_count = _entry_stats(entry)
        entries.append((entry, mtime, size_bytes, file_count))

    # 1) TTL cleanup
    if ttl_seconds > 0:
        for entry, mtime, size_bytes, file_count in list(entries):
            if now - mtime <= ttl_seconds:
                continue
            if _safe_delete_entry(base_dir, entry):
                stats["removed_entries"] += 1
                stats["removed_bytes"] += size_bytes
                stats["removed_files"] += file_count
                entries.remove((entry, mtime, size_bytes, file_count))

    # 2) Optional quotas cleanup (oldest first)
    total_bytes = sum(item[2] for item in entries)
    total_files = sum(item[3] for item in entries)
    if (max_total_bytes > 0 and total_bytes > max_total_bytes) or (max_file_count > 0 and total_files > max_file_count):
        entries.sort(key=lambda item: item[1])  # oldest first
        for entry, mtime, size_bytes, file_count in entries:
            if (max_total_bytes <= 0 or total_bytes <= max_total_bytes) and (max_file_count <= 0 or total_files <= max_file_count):
                break
            if _safe_delete_entry(base_dir, entry):
                stats["removed_entries"] += 1
                stats["removed_bytes"] += size_bytes
                stats["removed_files"] += file_count
                total_bytes -= size_bytes
                total_files -= file_count

    if stats["removed_entries"] > 0:
        logger.info(
            "dl_dir_cleanup removed_entries=%s removed_bytes=%s removed_files=%s",
            stats["removed_entries"],
            stats["removed_bytes"],
            stats["removed_files"],
            extra={"event": "dl_dir_cleanup", "status": "ok"},
        )
    return stats


def start_healthcheck_server(
    *,
    host: str,
    port: int,
    get_state: Callable[[], dict[str, Any]],
    logger: logging.Logger,
) -> ThreadingHTTPServer:
    """Start a lightweight background healthcheck HTTP server."""

    class _Handler(BaseHTTPRequestHandler):
        def _write_json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - stdlib handler API
            state = get_state()
            now = time.time()
            ready = bool(state.get("ready"))
            last_tick = float(state.get("last_monitor_tick") or 0.0)
            monitor_recent = (now - last_tick) < 300 if last_tick > 0 else ready
            healthy = bool(ready and monitor_recent)
            if self.path == "/healthz":
                self._write_json(200 if healthy else 503, {"ok": healthy, "ready": ready, "uptime_seconds": state.get("uptime_seconds", 0)})
                return
            if self.path == "/readyz":
                self._write_json(200 if ready else 503, {"ready": ready})
                return
            self._write_json(404, {"ok": False, "error": "not_found"})

        def log_message(self, format: str, *args):  # noqa: A003 - stdlib signature
            return

    server = ThreadingHTTPServer((host, port), _Handler)
    thread = threading.Thread(target=server.serve_forever, name="healthcheck-server", daemon=True)
    thread.start()
    logger.info("healthcheck server started host=%s port=%s", host, port, extra={"event": "healthcheck_start", "status": "ok"})
    return server
