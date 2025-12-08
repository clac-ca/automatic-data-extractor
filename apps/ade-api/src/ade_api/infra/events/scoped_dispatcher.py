"""Generic in-memory fan-out for scoped ADE event streams.

Build and run event dispatchers share identical mechanics:
- assign monotonically increasing sequence numbers per scope (run/build)
- broadcast the produced AdeEvent objects to any live subscribers

Feature-specific dispatchers keep their public method signatures and simply
delegate the common bits to this module.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from ade_api.schemas.events import AdeEvent

__all__ = ["EventSubscription", "ScopedEventDispatcher"]


@dataclass(slots=True)
class EventSubscription:
    """Async iterator over pushed events for a given scope."""

    scope_id: UUID
    _queue: asyncio.Queue[AdeEvent | None]
    _on_close: Callable[[UUID, asyncio.Queue[AdeEvent | None]], None]
    _closed: bool = False

    def __aiter__(self) -> AsyncIterator[AdeEvent]:
        return self._iterator()

    async def _iterator(self) -> AsyncIterator[AdeEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._on_close(self.scope_id, self._queue)
        await self._queue.put(None)


TSubscription = TypeVar("TSubscription", bound=EventSubscription)


class ScopedEventDispatcher:
    """Sequence assignment + subscriber fan-out shared by build/run dispatchers."""

    def __init__(self) -> None:
        self._sequence_by_scope: dict[UUID, int] = {}
        self._subscribers: dict[UUID, set[asyncio.Queue[AdeEvent | None]]] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}

    @asynccontextmanager
    async def subscribe_scope(
        self,
        scope_id: UUID,
        *,
        subscription_factory: Callable[
            [UUID, asyncio.Queue[AdeEvent | None], Callable[[UUID, asyncio.Queue[AdeEvent | None]], None]],
            TSubscription,
        ],
    ) -> AsyncIterator[TSubscription]:
        """Subscribe to a single scope and clean up automatically."""

        queue: asyncio.Queue[AdeEvent | None] = asyncio.Queue()
        self._subscribers.setdefault(scope_id, set()).add(queue)
        subscription = subscription_factory(scope_id, queue, self._remove_subscriber)
        try:
            yield subscription
        finally:
            await subscription.close()

    async def next_sequence(self, scope_id: UUID, *, last_sequence: Callable[[], int]) -> int:
        """Return the next sequence number for ``scope_id``."""

        lock = self._locks.setdefault(scope_id, asyncio.Lock())
        async with lock:
            if scope_id not in self._sequence_by_scope:
                self._sequence_by_scope[scope_id] = await asyncio.to_thread(last_sequence)
            self._sequence_by_scope[scope_id] += 1
            return self._sequence_by_scope[scope_id]

    async def publish(self, scope_id: UUID, event: AdeEvent) -> None:
        """Push an event to all live subscribers for ``scope_id``."""

        for queue in list(self._subscribers.get(scope_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    def _remove_subscriber(self, scope_id: UUID, queue: asyncio.Queue[AdeEvent | None]) -> None:
        subscribers = self._subscribers.get(scope_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(scope_id, None)
