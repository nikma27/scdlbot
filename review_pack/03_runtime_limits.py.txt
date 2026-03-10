"""Admission control, shutdown state and in-flight job registry."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass
class AdmissionDecision:
    allowed: bool
    reason_code: str = "ok"
    user_message: str = ""
    log_context: dict[str, Any] | None = None


@dataclass
class JobInfo:
    job_id: str
    job_type: str
    user_id: int
    chat_id: int
    request_type: str
    started_at: float
    query_preview: str = ""
    url_preview: str = ""


class RuntimeAdmission:
    """Thread-safe runtime controls for admission and active jobs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job_seq = 0
        self._active_jobs: dict[str, JobInfo] = {}
        self._shutdown_requested = False
        self._shutdown_started_at = 0.0
        self._shutdown_reason = ""
        self._shutdown_actor = ""

        self._user_events: dict[int, deque[float]] = defaultdict(deque)
        self._chat_events: dict[int, deque[float]] = defaultdict(deque)
        self._user_last_fingerprint: dict[int, tuple[str, float]] = {}
        self._chat_last_fingerprint: dict[int, tuple[str, float]] = {}

    def request_shutdown(self, *, reason: str, actor: str = "") -> bool:
        with self._lock:
            if self._shutdown_requested:
                return False
            self._shutdown_requested = True
            self._shutdown_started_at = time.time()
            self._shutdown_reason = reason
            self._shutdown_actor = actor
            return True

    def is_shutdown_requested(self) -> bool:
        with self._lock:
            return self._shutdown_requested

    def shutdown_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "shutdown_requested": self._shutdown_requested,
                "shutdown_started_at": self._shutdown_started_at,
                "shutdown_reason": self._shutdown_reason,
                "shutdown_actor": self._shutdown_actor,
            }

    def register_job(
        self,
        *,
        job_type: str,
        user_id: int,
        chat_id: int,
        request_type: str,
        query_preview: str = "",
        url_preview: str = "",
    ) -> str | None:
        with self._lock:
            if self._shutdown_requested:
                return None
            self._job_seq += 1
            job_id = f"job-{self._job_seq}"
            self._active_jobs[job_id] = JobInfo(
                job_id=job_id,
                job_type=job_type,
                user_id=user_id,
                chat_id=chat_id,
                request_type=request_type,
                started_at=time.time(),
                query_preview=query_preview,
                url_preview=url_preview,
            )
            return job_id

    def finish_job(self, job_id: str | None) -> None:
        if not job_id:
            return
        with self._lock:
            self._active_jobs.pop(job_id, None)

    def count_jobs(self, *, job_type: str | None = None, user_id: int | None = None, chat_id: int | None = None) -> int:
        with self._lock:
            jobs = self._active_jobs.values()
            if job_type is not None:
                jobs = [job for job in jobs if job.job_type == job_type]
            if user_id is not None:
                jobs = [job for job in jobs if job.user_id == user_id]
            if chat_id is not None:
                jobs = [job for job in jobs if job.chat_id == chat_id]
            return len(jobs)

    def active_jobs_snapshot(self) -> dict[str, Any]:
        with self._lock:
            by_type: dict[str, int] = defaultdict(int)
            for job in self._active_jobs.values():
                by_type[job.job_type] += 1
            return {
                "total": len(self._active_jobs),
                "by_type": dict(by_type),
            }

    def get_jobs(self, *, limit: int = 10) -> list[JobInfo]:
        with self._lock:
            jobs = sorted(self._active_jobs.values(), key=lambda job: job.started_at)
            return jobs[:limit]

    def get_jobs_for_user(self, user_id: int, *, limit: int = 20) -> list[JobInfo]:
        with self._lock:
            jobs = [job for job in self._active_jobs.values() if job.user_id == user_id]
            jobs.sort(key=lambda job: job.started_at)
            return jobs[:limit]

    @staticmethod
    def _prune_window(window: deque[float], now_ts: float, *, seconds: int) -> None:
        cutoff = now_ts - max(1, seconds)
        while window and window[0] < cutoff:
            window.popleft()

    def check_request_admission(
        self,
        *,
        request_type: str,
        user_id: int,
        chat_id: int,
        query_preview: str = "",
        url_preview: str = "",
        is_owner: bool = False,
        max_active_jobs_per_user: int,
        max_active_jobs_per_chat: int,
        max_global_active_jobs: int,
        user_request_cooldown_seconds: int,
        chat_request_cooldown_seconds: int,
        burst_request_limit: int,
        burst_window_seconds: int,
    ) -> AdmissionDecision:
        now_ts = time.time()
        fingerprint = f"{request_type}:{query_preview}:{url_preview}"[:240]
        with self._lock:
            if self._shutdown_requested:
                return AdmissionDecision(
                    allowed=False,
                    reason_code="shutdown",
                    user_message="Бот завершает работу, новые задачи временно не принимаются.",
                    log_context={"status": "shutdown"},
                )

            total_jobs = len(self._active_jobs)
            user_jobs = sum(1 for job in self._active_jobs.values() if job.user_id == user_id)
            chat_jobs = sum(1 for job in self._active_jobs.values() if job.chat_id == chat_id)

            if max_global_active_jobs > 0 and total_jobs >= max_global_active_jobs:
                return AdmissionDecision(
                    allowed=False,
                    reason_code="global_limit",
                    user_message="Сервер сейчас занят. Попробуйте немного позже.",
                    log_context={"active_total": total_jobs},
                )
            if max_active_jobs_per_user > 0 and user_jobs >= max_active_jobs_per_user:
                return AdmissionDecision(
                    allowed=False,
                    reason_code="user_limit",
                    user_message="У вас уже есть активные задачи. Дождитесь завершения.",
                    log_context={"active_user": user_jobs},
                )
            if max_active_jobs_per_chat > 0 and chat_jobs >= max_active_jobs_per_chat:
                return AdmissionDecision(
                    allowed=False,
                    reason_code="chat_limit",
                    user_message="В этом чате уже много активных задач. Попробуйте позже.",
                    log_context={"active_chat": chat_jobs},
                )

            if not is_owner:
                self._prune_window(self._user_events[user_id], now_ts, seconds=burst_window_seconds)
                self._prune_window(self._chat_events[chat_id], now_ts, seconds=burst_window_seconds)

                if burst_request_limit > 0 and (len(self._user_events[user_id]) + 1) > burst_request_limit:
                    return AdmissionDecision(
                        allowed=False,
                        reason_code="burst",
                        user_message="Слишком много запросов за короткое время. Подождите немного.",
                        log_context={"burst_user": len(self._user_events[user_id]) + 1},
                    )
                if burst_request_limit > 0 and (len(self._chat_events[chat_id]) + 1) > max(burst_request_limit, max_active_jobs_per_chat):
                    return AdmissionDecision(
                        allowed=False,
                        reason_code="burst",
                        user_message="Слишком много запросов в этом чате. Подождите немного.",
                        log_context={"burst_chat": len(self._chat_events[chat_id]) + 1},
                    )

                last_user = self._user_last_fingerprint.get(user_id)
                if last_user and last_user[0] == fingerprint and user_request_cooldown_seconds > 0:
                    if now_ts - last_user[1] < user_request_cooldown_seconds:
                        return AdmissionDecision(
                            allowed=False,
                            reason_code="cooldown",
                            user_message=f"Слишком часто. Подождите {user_request_cooldown_seconds} сек.",
                        )
                last_chat = self._chat_last_fingerprint.get(chat_id)
                if last_chat and last_chat[0] == fingerprint and chat_request_cooldown_seconds > 0:
                    if now_ts - last_chat[1] < chat_request_cooldown_seconds:
                        return AdmissionDecision(
                            allowed=False,
                            reason_code="cooldown",
                            user_message=f"Слишком часто для этого чата. Подождите {chat_request_cooldown_seconds} сек.",
                        )

                self._user_events[user_id].append(now_ts)
                self._chat_events[chat_id].append(now_ts)
                self._user_last_fingerprint[user_id] = (fingerprint, now_ts)
                self._chat_last_fingerprint[chat_id] = (fingerprint, now_ts)

            return AdmissionDecision(allowed=True, reason_code="ok")
