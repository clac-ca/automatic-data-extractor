"""WebSocket tailer + registry for document change feeds."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket

from ade_api.db import db
from ade_api.settings import Settings

from .change_feed import DocumentChangeCursorTooOld
from .schemas import DocumentChangeEntry
from .service import DocumentsService

logger = logging.getLogger(__name__)

TAILER_BASE_INTERVAL_SECONDS = 0.25
TAILER_MAX_INTERVAL_SECONDS = 2.0
TAILER_BATCH_LIMIT = 200
HEARTBEAT_SECONDS = 20.0
MAX_BUFFERED_EVENTS = 500
SEND_TIMEOUT_SECONDS = 5.0


@dataclass(slots=True)
class ChangeSubscriber:
    client_id: str
    workspace_id: UUID
    websocket: WebSocket
    stream_start_cursor: int
    ready: bool = False
    buffer: list[DocumentChangeEntry] = field(default_factory=list)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, message: dict[str, Any]) -> bool:
        async with self.send_lock:
            try:
                await asyncio.wait_for(
                    self.websocket.send_json(message),
                    timeout=SEND_TIMEOUT_SECONDS,
                )
                return True
            except Exception:
                return False

    async def close(self, code: int) -> None:
        async with self.send_lock:
            try:
                await self.websocket.close(code=code)
            except Exception:
                return


class DocumentsChangesRegistry:
    def __init__(self) -> None:
        self._channels: dict[UUID, dict[str, ChangeSubscriber]] = {}
        self._lock = asyncio.Lock()
        self._activity_event = asyncio.Event()

    def _signal_activity(self) -> None:
        self._activity_event.set()

    async def wait_for_activity(self, timeout: float | None = None) -> None:
        if self._activity_event.is_set():
            self._activity_event.clear()
            return
        try:
            await asyncio.wait_for(self._activity_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return
        finally:
            self._activity_event.clear()

    async def add_subscriber(
        self,
        *,
        workspace_id: UUID,
        websocket: WebSocket,
    ) -> ChangeSubscriber:
        subscriber = ChangeSubscriber(
            client_id=str(uuid4()),
            workspace_id=workspace_id,
            websocket=websocket,
            stream_start_cursor=-1,
        )
        async with self._lock:
            channel = self._channels.setdefault(workspace_id, {})
            channel[subscriber.client_id] = subscriber
        self._signal_activity()
        return subscriber

    async def remove_subscriber(
        self,
        *,
        workspace_id: UUID,
        client_id: str,
    ) -> None:
        async with self._lock:
            channel = self._channels.get(workspace_id)
            if not channel:
                return
            channel.pop(client_id, None)
            if not channel:
                self._channels.pop(workspace_id, None)
        self._signal_activity()

    async def active_workspaces(self) -> set[UUID]:
        async with self._lock:
            return {workspace_id for workspace_id, channel in self._channels.items() if channel}

    async def workspace_counts(self) -> dict[UUID, int]:
        async with self._lock:
            return {workspace_id: len(channel) for workspace_id, channel in self._channels.items() if channel}

    async def set_stream_start_cursor(
        self,
        *,
        workspace_id: UUID,
        client_id: str,
        cursor: int,
    ) -> None:
        async with self._lock:
            channel = self._channels.get(workspace_id)
            if not channel:
                return
            subscriber = channel.get(client_id)
            if not subscriber:
                return
            subscriber.stream_start_cursor = cursor
            if subscriber.buffer:
                subscriber.buffer = [
                    entry for entry in subscriber.buffer if int(entry.cursor) > cursor
                ]

    async def mark_ready(
        self,
        *,
        workspace_id: UUID,
        client_id: str,
    ) -> None:
        async with self._lock:
            channel = self._channels.get(workspace_id)
            if not channel:
                return
            subscriber = channel.get(client_id)
            if not subscriber:
                return
            subscriber.ready = True
            buffered = list(subscriber.buffer)
            subscriber.buffer = []

        if not buffered:
            return

        buffered.sort(key=lambda entry: int(entry.cursor))
        for entry in buffered:
            await self._send_event(subscriber, entry)

    async def broadcast_event(self, workspace_id: UUID, change: DocumentChangeEntry) -> None:
        cursor_value = int(change.cursor)
        async with self._lock:
            channel = self._channels.get(workspace_id)
            targets = list(channel.values()) if channel else []
            pending: list[ChangeSubscriber] = []
            resync_targets: list[ChangeSubscriber] = []
            for subscriber in targets:
                if not subscriber.ready:
                    if cursor_value > subscriber.stream_start_cursor:
                        subscriber.buffer.append(change)
                        if len(subscriber.buffer) > MAX_BUFFERED_EVENTS:
                            resync_targets.append(subscriber)
                    continue
                if cursor_value <= subscriber.stream_start_cursor:
                    continue
                pending.append(subscriber)

        if resync_targets:
            await self._broadcast_resync(
                workspace_id=workspace_id,
                latest_cursor=cursor_value,
                targets=resync_targets,
            )
            for subscriber in resync_targets:
                await self.remove_subscriber(
                    workspace_id=subscriber.workspace_id,
                    client_id=subscriber.client_id,
                )

        failures: list[ChangeSubscriber] = []
        for subscriber in pending:
            ok = await self._send_event(subscriber, change)
            if not ok:
                failures.append(subscriber)

        for subscriber in failures:
            await self.remove_subscriber(
                workspace_id=subscriber.workspace_id,
                client_id=subscriber.client_id,
            )

    async def broadcast_heartbeat(self) -> None:
        async with self._lock:
            targets = [subscriber for channel in self._channels.values() for subscriber in channel.values()]

        if not targets:
            return

        message = {
            "type": "heartbeat",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        failures: list[ChangeSubscriber] = []
        for subscriber in targets:
            if not await subscriber.send(message):
                failures.append(subscriber)

        for subscriber in failures:
            await self.remove_subscriber(
                workspace_id=subscriber.workspace_id,
                client_id=subscriber.client_id,
            )

    async def broadcast_resync(
        self,
        *,
        workspace_id: UUID,
        latest_cursor: int,
        close_code: int,
    ) -> None:
        async with self._lock:
            channel = self._channels.get(workspace_id)
            targets = list(channel.values()) if channel else []

        await self._broadcast_resync(
            workspace_id=workspace_id,
            latest_cursor=latest_cursor,
            targets=targets,
            close_code=close_code,
        )

        for subscriber in targets:
            await self.remove_subscriber(
                workspace_id=subscriber.workspace_id,
                client_id=subscriber.client_id,
            )

    async def send_resync(
        self,
        *,
        subscriber: ChangeSubscriber,
        latest_cursor: int,
        close_code: int,
    ) -> None:
        await self._broadcast_resync(
            workspace_id=subscriber.workspace_id,
            latest_cursor=latest_cursor,
            targets=[subscriber],
            close_code=close_code,
        )
        await self.remove_subscriber(
            workspace_id=subscriber.workspace_id,
            client_id=subscriber.client_id,
        )

    async def _broadcast_resync(
        self,
        *,
        workspace_id: UUID,
        latest_cursor: int,
        targets: list[ChangeSubscriber],
        close_code: int = 4409,
    ) -> None:
        if not targets:
            return

        message = {
            "type": "error",
            "code": "resync_required",
            "latestCursor": str(latest_cursor),
        }

        for subscriber in targets:
            await subscriber.send(message)
            await subscriber.close(close_code)

    async def _send_event(self, subscriber: ChangeSubscriber, change: DocumentChangeEntry) -> bool:
        message = {
            "type": "event",
            "workspaceId": str(subscriber.workspace_id),
            "change": change.model_dump(by_alias=True, exclude_none=True),
        }
        return await subscriber.send(message)


class DocumentsChangesTailer:
    def __init__(
        self,
        *,
        registry: DocumentsChangesRegistry,
        settings: Settings,
        close_code_resync: int,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._close_code_resync = close_code_resync
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._workspace_cursors: dict[UUID, int] = {}
        self._last_heartbeat = 0.0

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        sleep_seconds = TAILER_BASE_INTERVAL_SECONDS

        while not self._stop_event.is_set():
            active_workspaces = await self._registry.active_workspaces()
            for workspace_id in list(self._workspace_cursors):
                if workspace_id not in active_workspaces:
                    self._workspace_cursors.pop(workspace_id, None)

            if not active_workspaces:
                await self._registry.wait_for_activity(timeout=sleep_seconds)
                continue

            had_changes = False
            now = time.monotonic()
            async with db.sessionmaker() as session:
                service = DocumentsService(session=session, settings=self._settings)

                for workspace_id in active_workspaces:
                    cursor = self._workspace_cursors.get(workspace_id)
                    if cursor is None:
                        cursor = await service._changes.current_cursor(workspace_id=workspace_id)
                        self._workspace_cursors[workspace_id] = cursor
                        continue

                    try:
                        page = await service.list_document_changes(
                            workspace_id=workspace_id,
                            cursor_token=str(cursor),
                            limit=TAILER_BATCH_LIMIT,
                        )
                    except DocumentChangeCursorTooOld as exc:
                        logger.warning(
                            "documents.changes.resync_required",
                            extra={"workspace_id": str(workspace_id), "latest_cursor": exc.latest_cursor},
                        )
                        self._workspace_cursors[workspace_id] = exc.latest_cursor
                        await self._registry.broadcast_resync(
                            workspace_id=workspace_id,
                            latest_cursor=exc.latest_cursor,
                            close_code=self._close_code_resync,
                        )
                        continue

                    self._workspace_cursors[workspace_id] = int(page.next_cursor)

                    if not page.items:
                        continue

                    had_changes = True
                    for change in _coalesce_changes(page.items):
                        await self._registry.broadcast_event(workspace_id, change)

                if now - self._last_heartbeat >= HEARTBEAT_SECONDS:
                    await self._registry.broadcast_heartbeat()
                    counts = await self._registry.workspace_counts()
                    for workspace_id, connection_count in counts.items():
                        latest_cursor = await service._changes.current_cursor(
                            workspace_id=workspace_id
                        )
                        tailer_cursor = self._workspace_cursors.get(workspace_id, latest_cursor)
                        logger.debug(
                            "documents.changes.tailer.stats",
                            extra={
                                "workspace_id": str(workspace_id),
                                "connections": connection_count,
                                "lag": max(latest_cursor - tailer_cursor, 0),
                            },
                        )
                    self._last_heartbeat = now

            if had_changes:
                sleep_seconds = TAILER_BASE_INTERVAL_SECONDS
            else:
                sleep_seconds = min(TAILER_MAX_INTERVAL_SECONDS, sleep_seconds * 1.5)

            await self._registry.wait_for_activity(timeout=sleep_seconds)


class DocumentsChangesHub:
    def __init__(self, *, settings: Settings, close_code_resync: int) -> None:
        self._registry = DocumentsChangesRegistry()
        self._tailer = DocumentsChangesTailer(
            registry=self._registry,
            settings=settings,
            close_code_resync=close_code_resync,
        )

    async def register(self, *, workspace_id: UUID, websocket: WebSocket) -> ChangeSubscriber:
        subscriber = await self._registry.add_subscriber(
            workspace_id=workspace_id,
            websocket=websocket,
        )
        await self._tailer.start()
        return subscriber

    async def unregister(self, *, workspace_id: UUID, client_id: str) -> None:
        await self._registry.remove_subscriber(
            workspace_id=workspace_id,
            client_id=client_id,
        )

    @property
    def registry(self) -> DocumentsChangesRegistry:
        return self._registry


_DOCUMENTS_CHANGES_HUB: DocumentsChangesHub | None = None


def get_documents_changes_hub(*, settings: Settings, close_code_resync: int) -> DocumentsChangesHub:
    global _DOCUMENTS_CHANGES_HUB
    if _DOCUMENTS_CHANGES_HUB is None:
        _DOCUMENTS_CHANGES_HUB = DocumentsChangesHub(
            settings=settings,
            close_code_resync=close_code_resync,
        )
    return _DOCUMENTS_CHANGES_HUB


def _coalesce_changes(items: list[DocumentChangeEntry]) -> list[DocumentChangeEntry]:
    latest_by_doc: dict[str, DocumentChangeEntry] = {}
    for item in items:
        doc_id = item.document_id or (item.row.id if item.row else None)
        key = doc_id or item.cursor
        latest_by_doc[str(key)] = item
    return sorted(latest_by_doc.values(), key=lambda entry: int(entry.cursor))


__all__ = ["get_documents_changes_hub", "DocumentsChangesHub"]
