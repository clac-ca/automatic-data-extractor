"""Best-effort document change notifications via Postgres LISTEN/NOTIFY."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import threading
import time
from typing import Any, Callable

import psycopg
from fastapi import FastAPI, Request
from sqlalchemy.engine import URL, make_url
from ade_api.settings import Settings

from .changes import DOCUMENT_CHANGES_CHANNEL

# Optional dependency (Managed Identity)
try:  # pragma: no cover - optional dependency
    from azure.identity import DefaultAzureCredential  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    DefaultAzureCredential = None  # type: ignore[assignment]

DEFAULT_AZURE_PG_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
DEFAULT_POLL_SECONDS = 1.0
DEFAULT_QUEUE_SIZE = 200
MAX_BACKOFF_SECONDS = 30.0

logger = logging.getLogger(__name__)


def _normalize_psycopg_url(url: URL) -> URL:
    if url.drivername in {"postgresql", "postgres"}:
        return url
    if url.drivername.startswith("postgresql+"):
        return url.set(drivername="postgresql")
    return url


def _get_azure_postgres_access_token() -> str:
    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed Identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=password."
        )
    credential = DefaultAzureCredential()
    return credential.get_token(DEFAULT_AZURE_PG_SCOPE).token


def _build_listen_connect_kwargs(settings: Settings) -> dict[str, Any]:
    url = _normalize_psycopg_url(make_url(str(settings.database_url)))
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
        params["password"] = _get_azure_postgres_access_token()
        params.setdefault("sslmode", "require")
    if settings.database_sslrootcert:
        params["sslrootcert"] = settings.database_sslrootcert

    return params


EventPayload = dict[str, Any]
EventQueue = asyncio.Queue[EventPayload]


class DocumentChangesHub:
    """Background LISTEN loop that fans out document change notifications."""

    def __init__(
        self,
        *,
        settings: Settings,
        channel: str = DOCUMENT_CHANGES_CHANNEL,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        queue_size: int = DEFAULT_QUEUE_SIZE,
    ) -> None:
        self._settings = settings
        self._channel = channel
        self._poll_seconds = max(0.1, float(poll_seconds))
        self._queue_size = max(10, int(queue_size))
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[str, set[EventQueue]] = {}

    def start(self, *, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop_event.set()
        self._thread.join(timeout=timeout)

    def subscribe(self, workspace_id: str) -> tuple[EventQueue, Callable[[], None]]:
        queue: EventQueue = asyncio.Queue(maxsize=self._queue_size)
        with self._lock:
            self._subscribers.setdefault(workspace_id, set()).add(queue)
            subscriber_count = len(self._subscribers.get(workspace_id, set()))
        logger.info(
            "documents.changes.subscribed",
            extra={"workspace_id": workspace_id, "subscribers": subscriber_count},
        )

        def _unsubscribe() -> None:
            with self._lock:
                queues = self._subscribers.get(workspace_id)
                if not queues:
                    return
                queues.discard(queue)
                if not queues:
                    self._subscribers.pop(workspace_id, None)
                subscriber_count = len(queues) if queues else 0
            logger.info(
                "documents.changes.unsubscribed",
                extra={"workspace_id": workspace_id, "subscribers": subscriber_count},
            )

        return queue, _unsubscribe

    def _enqueue(self, queue: EventQueue, payload: EventPayload) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(
                "documents.changes.queue_full",
                extra={"workspace_id": payload.get("workspaceId")},
            )

    def _publish(self, workspace_id: str, payload: EventPayload) -> None:
        loop = self._loop
        if loop is None:
            return
        with self._lock:
            queues = list(self._subscribers.get(workspace_id, set()))
        for queue in queues:
            try:
                loop.call_soon_threadsafe(self._enqueue, queue, payload)
            except RuntimeError:
                continue

    def _parse_payload(self, payload: str) -> tuple[str, EventPayload] | None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        workspace_id = data.get("workspaceId")
        document_id = data.get("documentId")
        op = data.get("op")
        change_id = data.get("id")
        if not workspace_id or not document_id or not op or change_id is None:
            return None
        try:
            change_id = int(change_id)
            if change_id < 0:
                return None
        except (ValueError, TypeError):
            return None

        return str(workspace_id), {
            "workspaceId": str(workspace_id),
            "documentId": str(document_id),
            "op": str(op),
            "id": str(change_id),
        }

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            connection = None
            try:
                connect_kwargs = _build_listen_connect_kwargs(self._settings)
                connection = psycopg.connect(**connect_kwargs, autocommit=True)
                with connection.cursor() as cursor:
                    cursor.execute(f"LISTEN {self._channel}")
                logger.info("documents.changes.listen channel=%s", self._channel)
                backoff = 1.0

                while not self._stop_event.is_set():
                    for notification in connection.notifies(timeout=self._poll_seconds):
                        parsed = self._parse_payload(notification.payload)
                        if parsed:
                            workspace_id, payload = parsed
                            self._publish(workspace_id, payload)
            except Exception:
                logger.exception("documents.changes.listen_failed retry_in=%ss", backoff)
                time.sleep(backoff + random.random())
                backoff = min(MAX_BACKOFF_SECONDS, backoff * 2)
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass


def _resolve_app(app_or_request: FastAPI | Request) -> FastAPI:
    if isinstance(app_or_request, FastAPI):
        return app_or_request
    return app_or_request.app


def get_document_changes_hub(app_or_request: FastAPI | Request) -> DocumentChangesHub:
    app = _resolve_app(app_or_request)
    hub = getattr(app.state, "document_changes_hub", None)
    if hub is None:
        raise RuntimeError("Document changes hub is not initialized.")
    return hub


__all__ = [
    "DocumentChangesHub",
    "get_document_changes_hub",
]
