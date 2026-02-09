from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import WebSocket

PresenceContext = dict[str, Any]
ChannelKey = tuple[UUID, str, str]


@dataclass(slots=True)
class PresenceParticipant:
    client_id: str
    user_id: UUID
    display_name: str | None
    email: str | None
    status: str
    scope: str
    context: PresenceContext
    presence: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None
    editing: dict[str, Any] | None = None

    def to_public(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "user_id": str(self.user_id),
            "display_name": self.display_name,
            "email": self.email,
            "status": self.status,
            "presence": self.presence,
            "selection": self.selection,
            "editing": self.editing,
        }


@dataclass(slots=True)
class PresenceChannel:
    participants: dict[str, PresenceParticipant] = field(default_factory=dict)
    sockets: dict[str, WebSocket] = field(default_factory=dict)


class PresenceRegistry:
    def __init__(self) -> None:
        self._channels: dict[ChannelKey, PresenceChannel] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _normalize_context(context: PresenceContext | None) -> tuple[PresenceContext, str]:
        if context is None:
            normalized: PresenceContext = {}
        elif not isinstance(context, dict):
            raise ValueError("Presence context must be an object")
        else:
            normalized = {str(key): value for key, value in context.items()}
        key = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
        return normalized, key

    async def join(
        self,
        *,
        workspace_id: UUID,
        participant: PresenceParticipant,
        websocket: WebSocket,
    ) -> tuple[ChannelKey, list[dict[str, Any]]]:
        normalized_context, context_key = self._normalize_context(participant.context)
        participant.context = normalized_context
        channel_key: ChannelKey = (workspace_id, participant.scope, context_key)

        async with self._lock:
            channel = self._channels.setdefault(channel_key, PresenceChannel())
            channel.participants[participant.client_id] = participant
            channel.sockets[participant.client_id] = websocket
            snapshot = [item.to_public() for item in channel.participants.values()]
        return channel_key, snapshot

    async def update(
        self,
        *,
        channel_key: ChannelKey,
        client_id: str,
        update_type: str,
        payload: dict[str, Any],
    ) -> PresenceParticipant | None:
        async with self._lock:
            channel = self._channels.get(channel_key)
            if channel is None:
                return None
            participant = channel.participants.get(client_id)
            if participant is None:
                return None

            if update_type == "presence":
                participant.presence = payload
                status = payload.get("status")
                if isinstance(status, str) and status.strip():
                    participant.status = status
            elif update_type == "selection":
                participant.selection = payload
            elif update_type == "editing":
                participant.editing = payload

            return participant

    async def leave(self, *, channel_key: ChannelKey, client_id: str) -> PresenceParticipant | None:
        async with self._lock:
            channel = self._channels.get(channel_key)
            if channel is None:
                return None
            participant = channel.participants.pop(client_id, None)
            channel.sockets.pop(client_id, None)
            if not channel.participants:
                self._channels.pop(channel_key, None)
        return participant

    async def broadcast(
        self,
        *,
        channel_key: ChannelKey,
        message: dict[str, Any],
        skip_client_id: str | None = None,
    ) -> None:
        async with self._lock:
            channel = self._channels.get(channel_key)
            if channel is None:
                return
            targets = list(channel.sockets.items())

        failures: list[str] = []
        for client_id, socket in targets:
            if skip_client_id and client_id == skip_client_id:
                continue
            try:
                await socket.send_json(message)
            except Exception:
                failures.append(client_id)

        if failures:
            for client_id in failures:
                await self.leave(channel_key=channel_key, client_id=client_id)


_PRESENCE_REGISTRY: PresenceRegistry | None = None


def get_presence_registry() -> PresenceRegistry:
    global _PRESENCE_REGISTRY
    if _PRESENCE_REGISTRY is None:
        _PRESENCE_REGISTRY = PresenceRegistry()
    return _PRESENCE_REGISTRY


__all__ = [
    "ChannelKey",
    "PresenceParticipant",
    "PresenceRegistry",
    "get_presence_registry",
]
