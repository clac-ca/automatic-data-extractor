"""Lightweight event dispatcher used for ADE domain messages."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Awaitable, Callable, Mapping


MessageHandler = Callable[["Message"], Awaitable[None]]


@dataclass(slots=True)
class Message:
    """Envelope passed to subscribed handlers when an event is published."""

    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.payload = MappingProxyType(dict(self.payload))
        self.metadata = MappingProxyType(dict(self.metadata))


class MessageHub:
    """In-memory dispatcher that fans out events to registered handlers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[MessageHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: MessageHandler) -> None:
        """Register ``handler`` for ``event_name`` if not already registered."""

        handlers = self._subscribers[event_name]
        if handler not in handlers:
            handlers.append(handler)

    def subscribe_all(self, handler: MessageHandler) -> None:
        """Register ``handler`` for every event emitted by the hub."""

        self.subscribe("*", handler)

    def unsubscribe(self, event_name: str, handler: MessageHandler) -> None:
        """Remove ``handler`` from ``event_name`` subscribers when present."""

        handlers = self._subscribers.get(event_name)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            self._subscribers.pop(event_name, None)

    def clear(self) -> None:
        """Remove all registered subscribers."""

        self._subscribers.clear()

    async def publish(
        self,
        name: str,
        payload: Mapping[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Dispatch ``payload`` to subscribers registered for ``name``."""

        message = Message(
            name=name,
            payload=payload or {},
            correlation_id=correlation_id,
            metadata=metadata or {},
        )
        handlers = list(self._subscribers.get(name, ()))
        wildcard_handlers = self._subscribers.get("*", [])
        if wildcard_handlers:
            handlers.extend(wildcard_handlers)

        if not handlers:
            return

        seen: set[MessageHandler] = set()
        ordered_handlers: list[MessageHandler] = []
        for handler in handlers:
            if handler in seen:
                continue
            seen.add(handler)
            ordered_handlers.append(handler)

        for handler in ordered_handlers:
            await handler(message)


__all__ = ["Message", "MessageHandler", "MessageHub"]
