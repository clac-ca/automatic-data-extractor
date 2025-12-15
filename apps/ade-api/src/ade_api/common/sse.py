"""Server-Sent Events (SSE) encoding helpers."""

from __future__ import annotations

from typing import Any

from ade_api.common.encoding import json_bytes


def sse_bytes(payload: bytes, *, event_id: str | int | None = None) -> bytes:
    """Format raw bytes as an SSE message.

    We intentionally omit the SSE `event:` field and rely on the JSON envelope's `event`
    attribute. This keeps browser `EventSource.onmessage` compatible.
    """

    parts: list[bytes] = []
    if event_id is not None:
        parts.append(f"id: {event_id}\n".encode("utf-8"))
    parts.append(b"data: ")
    parts.append(payload)
    parts.append(b"\n\n")
    return b"".join(parts)


def sse_json(event: Any, *, event_id: str | int | None = None) -> bytes:
    """Encode an object as compact JSON and wrap it as an SSE message."""

    return sse_bytes(json_bytes(event), event_id=event_id)


__all__ = ["sse_bytes", "sse_json"]

