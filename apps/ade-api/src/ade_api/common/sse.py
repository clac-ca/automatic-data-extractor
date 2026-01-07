"""Server-Sent Events (SSE) encoding helpers.

These helpers emit EventSource-compatible payload dictionaries for
``EventSourceResponse``. The ``data`` field should always be text, so we
serialize JSON to a compact string instead of raw bytes.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from watchfiles import awatch

from ade_api.common.encoding import json_dumps
from ade_api.common.events import strip_sequence

WATCH_DEBOUNCE_MS = 50
WATCH_STEP_MS = 50
WATCH_TIMEOUT_MS = 500


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


async def stream_ndjson_events(
    *,
    path: Path,
    start_sequence: int = 0,
    stop_events: set[str] | None = None,
    ping_interval: float = 15.0,
) -> AsyncIterator[dict[str, str]]:
    """Tail an NDJSON event log file and yield SSE messages."""

    stop_events = stop_events or set()
    last_sequence = start_sequence
    cursor = 0
    last_ping = time.monotonic()

    def _handle_event(event: dict[str, Any]) -> tuple[dict[str, str] | None, bool]:
        nonlocal cursor, last_sequence
        cursor += 1
        seq = event.get("sequence")
        if not isinstance(seq, int):
            seq = cursor
            event["sequence"] = seq
        if seq <= last_sequence:
            return None, False
        last_sequence = seq
        payload = strip_sequence(event)
        message = sse_json(
            str(event.get("event") or "message"),
            payload,
            event_id=last_sequence,
        )
        return message, event.get("event") in stop_events

    if not path.exists():
        # The worker pre-creates the log file; this only runs if a client connects early.
        yield sse_text("ping", "waiting")
        last_ping = time.monotonic()
        wait_step = min(0.25, ping_interval)
        while not path.exists():
            await asyncio.sleep(wait_step)
            now = time.monotonic()
            if now - last_ping >= ping_interval:
                yield sse_text("ping", "waiting")
                last_ping = now
        last_ping = time.monotonic()

    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            event = _parse_event_line(raw)
            if event is None:
                continue
            message, should_stop = _handle_event(event)
            if message is None:
                continue
            yield message
            if should_stop:
                return

        watcher = awatch(
            path,
            debounce=WATCH_DEBOUNCE_MS,
            step=WATCH_STEP_MS,
            rust_timeout=WATCH_TIMEOUT_MS,
            yield_on_timeout=True,
        )
        while True:
            line = handle.readline()
            if line:
                event = _parse_event_line(line)
                if event is None:
                    continue
                message, should_stop = _handle_event(event)
                if message is None:
                    continue
                yield message
                if should_stop:
                    return
                continue

            try:
                await watcher.__anext__()
            except StopAsyncIteration:
                return

            now = time.monotonic()
            if now - last_ping >= ping_interval:
                yield sse_text("ping", "keep-alive")
                last_ping = now


def _parse_event_line(raw: str) -> dict[str, Any] | None:
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if "event" not in parsed:
        return None
    return parsed


__all__ = ["sse_bytes", "sse_json", "sse_text", "stream_ndjson_events"]
