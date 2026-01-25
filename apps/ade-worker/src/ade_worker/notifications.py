"""Postgres LISTEN/NOTIFY helper for waking workers on queued runs."""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

import psycopg
from sqlalchemy.engine import URL, make_url

from .db.azure_postgres_auth import get_azure_postgres_access_token
from .settings import Settings

logger = logging.getLogger("ade_worker")


@dataclass(slots=True)
class WakeSignal:
    """Event helper that tracks whether we were woken by NOTIFY."""

    _event: threading.Event
    _lock: threading.Lock
    _notify_count: int

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._notify_count = 0

    def notify(self) -> None:
        with self._lock:
            self._notify_count += 1
        self._event.set()

    def work_done(self) -> None:
        self._event.set()

    def wait(self, timeout: float) -> bool:
        fired = self._event.wait(timeout)
        with self._lock:
            notified = self._notify_count > 0
            self._notify_count = 0
            self._event.clear()
        return bool(fired and notified)


def _normalize_psycopg_url(url: URL) -> URL:
    if url.drivername in {"postgresql", "postgres"}:
        return url
    if url.drivername.startswith("postgresql+"):
        return url.set(drivername="postgresql")
    return url


def _build_listen_connect_kwargs(settings: Settings) -> dict[str, Any]:
    url = _normalize_psycopg_url(make_url(settings.database_url))
    params: dict[str, Any] = {
        "host": url.host,
        "port": url.port,
        "user": url.username,
        "dbname": url.database,
    }
    if url.password:
        params["password"] = url.password
    params.update(url.query or {})

    if settings.database_auth_mode == "managed_identity":
        params["password"] = get_azure_postgres_access_token()
        params.setdefault("sslmode", "require")
    if settings.database_sslrootcert:
        params["sslrootcert"] = settings.database_sslrootcert

    return params


class RunQueueListener:
    """Background LISTEN loop that wakes the worker on queued runs."""

    def __init__(
        self,
        *,
        settings: Settings,
        wake_signal: WakeSignal,
        channel: str = "ade_run_queued",
        poll_seconds: float = 1.0,
    ) -> None:
        self._settings = settings
        self._wake_signal = wake_signal
        self._channel = channel
        self._poll_seconds = max(0.1, float(poll_seconds))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            conn = None
            try:
                params = _build_listen_connect_kwargs(self._settings)
                conn = psycopg.connect(**params, autocommit=True)
                with conn.cursor() as cur:
                    cur.execute(f"LISTEN {self._channel}")
                logger.info("run.notify.listen channel=%s", self._channel)
                backoff = 1.0

                while not self._stop.is_set():
                    saw_notify = False
                    for _notify in conn.notifies(timeout=self._poll_seconds):
                        saw_notify = True
                    if saw_notify:
                        self._wake_signal.notify()
            except Exception:
                logger.exception("run.notify.listen_failed retry_in=%ss", backoff)
                time.sleep(backoff + random.random())
                backoff = min(30.0, backoff * 2)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass


__all__ = ["RunQueueListener", "WakeSignal"]
