"""Server-Sent Events (SSE) encoding helpers.

These helpers emit EventSource-compatible payload dictionaries for
``EventSourceResponse``. The ``data`` field should always be text, so we
serialize JSON to a compact string instead of raw bytes.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import asyncio
import json
from pathlib import Path

from watchfiles import awatch

from ade_api.common.events import strip_sequence

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

    while not path.exists():
        yield sse_text("ping", "waiting")
        await asyncio.sleep(ping_interval)

    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            event = _parse_event_line(raw)
            if event is None:
                continue
            cursor += 1
            seq = event.get("sequence")
            if not isinstance(seq, int):
                seq = cursor
                event["sequence"] = seq
            if seq <= start_sequence:
                continue
            last_sequence = seq
            payload = strip_sequence(event)
            yield sse_json(
                str(event.get("event") or "message"),
                payload,
                event_id=last_sequence,
            )
            if event.get("event") in stop_events:
                return

        watcher = awatch(path.parent)
        while True:
            line = handle.readline()
            if line:
                event = _parse_event_line(line)
                if event is None:
                    continue
                cursor += 1
                seq = event.get("sequence")
                if isinstance(seq, int):
                    if seq <= last_sequence:
                        continue
                    last_sequence = seq
                else:
                    last_sequence += 1
                payload = strip_sequence(event)
                yield sse_json(
                    str(event.get("event") or "message"),
                    payload,
                    event_id=last_sequence,
                )
                if event.get("event") in stop_events:
                    return
                continue

            try:
                await asyncio.wait_for(watcher.__anext__(), timeout=ping_interval)
            except asyncio.TimeoutError:
                yield sse_text("ping", "keep-alive")
            except StopAsyncIteration:
                return


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
