"""Base interfaces for queue adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True, frozen=True)
class QueueMessage:
    """Represents a queued job fetched from an adapter."""

    id: str
    name: str
    payload: Mapping[str, Any]
    enqueued_at: datetime
    attempts: int = 0


class QueueAdapter(ABC):
    """Protocol implemented by ADE queue adapters."""

    @abstractmethod
    async def enqueue(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> QueueMessage:
        """Persist a new message for future processing."""

    @abstractmethod
    async def claim(self) -> QueueMessage | None:
        """Return the next available job for processing, or ``None`` when idle."""

    @abstractmethod
    async def ack(self, message: QueueMessage) -> None:
        """Mark ``message`` as successfully processed."""

    @abstractmethod
    async def fail(self, message: QueueMessage, *, reason: str | None = None) -> None:
        """Record a failure for ``message`` and release it for retry."""
