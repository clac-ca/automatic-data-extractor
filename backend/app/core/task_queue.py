"""In-memory task queue scaffolding for background job execution."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping

TaskHandler = Callable[["TaskMessage"], Awaitable[None]]


@dataclass(slots=True, frozen=True)
class TaskMessage:
    """Envelope describing a queued background task."""

    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    enqueued_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TaskQueue:
    """Simple async-friendly queue with subscriber hooks."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pending: deque[TaskMessage] = deque()
        self._subscribers: list[TaskHandler] = []

    async def enqueue(
        self,
        name: str,
        payload: Mapping[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TaskMessage:
        """Append a task to the queue and fan out to subscribers."""

        message = TaskMessage(
            name=name,
            payload=dict(payload or {}),
            correlation_id=correlation_id,
            metadata=dict(metadata or {}),
        )

        async with self._lock:
            self._pending.append(message)
            subscribers = list(self._subscribers)

        try:
            for handler in subscribers:
                await handler(message)
        finally:
            if subscribers:
                async with self._lock:
                    try:
                        self._pending.remove(message)
                    except ValueError:
                        pass

        return message

    async def drain(self) -> list[TaskMessage]:
        """Return and clear all pending tasks."""

        async with self._lock:
            items = list(self._pending)
            self._pending.clear()
        return items

    async def clear(self) -> None:
        """Remove all queued tasks without returning them."""

        await self.drain()

    async def snapshot(self) -> list[TaskMessage]:
        """Return the current pending tasks without mutating the queue."""

        async with self._lock:
            return list(self._pending)

    def subscribe(self, handler: TaskHandler) -> None:
        """Register ``handler`` for future enqueued tasks."""

        if handler not in self._subscribers:
            self._subscribers.append(handler)

    def unsubscribe(self, handler: TaskHandler) -> None:
        """Remove ``handler`` when previously subscribed."""

        try:
            self._subscribers.remove(handler)
        except ValueError:
            return

    def clear_subscribers(self) -> None:
        """Remove all subscriber callbacks."""

        self._subscribers.clear()


__all__ = ["TaskQueue", "TaskHandler", "TaskMessage"]
