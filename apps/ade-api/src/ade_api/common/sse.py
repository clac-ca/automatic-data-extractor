"""Server-Sent Events (SSE) encoding helpers.

These helpers emit EventSource-compatible payload dictionaries for
``EventSourceResponse``. The ``data`` field should always be text, so we
serialize JSON to a compact string instead of raw bytes.
"""

from __future__ import annotations

from typing import Any

from ade_api.common.encoding import json_dumps


def _build_event(
    data: str,
    *,
    event: str | None = None,
    event_id: str | int | None = None,
) -> dict[str, str]:
    message = {"data": data}
    if event is not None:
        message["event"] = event
    if event_id is not None:
        message["id"] = str(event_id)
    return message


def sse_bytes(
    payload: bytes,
    *,
    event: str | None = None,
    event_id: str | int | None = None,
) -> dict[str, str]:
    """Format raw bytes as an SSE message dict."""

    return _build_event(
        payload.decode("utf-8", errors="replace"),
        event=event,
        event_id=event_id,
    )


def sse_text(
    event: str,
    text: str,
    *,
    event_id: str | int | None = None,
) -> dict[str, str]:
    """Encode UTF-8 text as an SSE message dict."""

    return _build_event(text, event=event, event_id=event_id)


def sse_json(
    event: str,
    data: Any,
    *,
    event_id: str | int | None = None,
) -> dict[str, str]:
    """Encode an object as compact JSON and wrap it as an SSE message dict."""

    return _build_event(json_dumps(data), event=event, event_id=event_id)


__all__ = ["sse_bytes", "sse_json", "sse_text"]
