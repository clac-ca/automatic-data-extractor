"""Server-Sent Events (SSE) encoding helpers.

This module intentionally keeps the API small and "standard SSE":
- `id:` is used for monotonic sequencing.
- `event:` carries the event name/type (so clients can use `EventSource.addEventListener`).
- `data:` contains UTF-8 text (often JSON, sometimes plain text).

Multi-line payloads are split across multiple `data:` lines per the SSE spec.
"""

from __future__ import annotations

from typing import Any

from ade_api.common.encoding import json_bytes


def sse_bytes(
    payload: bytes,
    *,
    event: str | None = None,
    event_id: str | int | None = None,
) -> bytes:
    """Format raw bytes as an SSE message."""

    parts: list[bytes] = []
    if event_id is not None:
        parts.append(f"id: {event_id}\n".encode())
    if event is not None:
        parts.append(f"event: {event}\n".encode())
    for line in payload.split(b"\n"):
        parts.append(b"data: ")
        parts.append(line)
        parts.append(b"\n")
    parts.append(b"\n")
    return b"".join(parts)


def sse_text(
    event: str,
    text: str,
    *,
    event_id: str | int | None = None,
) -> bytes:
    """Encode UTF-8 text as an SSE message."""

    return sse_bytes(text.encode("utf-8"), event=event, event_id=event_id)


def sse_json(
    event: str,
    data: Any,
    *,
    event_id: str | int | None = None,
) -> bytes:
    """Encode an object as compact JSON and wrap it as an SSE message."""

    return sse_bytes(json_bytes(data), event=event, event_id=event_id)


__all__ = ["sse_bytes", "sse_json", "sse_text"]
