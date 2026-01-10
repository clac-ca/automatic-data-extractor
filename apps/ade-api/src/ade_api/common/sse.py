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

from ade_api.common.encoding import json_dumps

DEFAULT_READ_CHUNK_SIZE = 64 * 1024
DEFAULT_POLL_INTERVAL = 0.25


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
    start_offset: int = 0,
    stop_events: set[str] | None = None,
    ping_interval: float = 15.0,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    read_chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
) -> AsyncIterator[dict[str, str]]:
    """Tail an NDJSON event log file and yield SSE messages using byte offsets."""

    stop_events = stop_events or set()
    cursor = max(0, start_offset)
    last_ping = time.monotonic()
    buffer = b""
    wait_step = min(poll_interval, ping_interval)

    try:
        while True:
            if not path.exists():
                # The worker pre-creates the log file; this only runs if a client connects early.
                yield sse_text("ping", "waiting")
                last_ping = time.monotonic()
                while not path.exists():
                    await asyncio.sleep(wait_step)
                    now = time.monotonic()
                    if now - last_ping >= ping_interval:
                        yield sse_text("ping", "waiting")
                        last_ping = now
                last_ping = time.monotonic()

            try:
                stat = path.stat()
            except FileNotFoundError:
                continue

            if cursor > stat.st_size:
                cursor = stat.st_size
                buffer = b""

            file_id = (stat.st_dev, stat.st_ino)
            with path.open("rb") as handle:
                handle.seek(cursor)
                while True:
                    chunk = handle.read(read_chunk_size)
                    if chunk:
                        buffer += chunk
                        lines = buffer.splitlines(keepends=True)
                        buffer = b""
                        for line in lines:
                            if not line.endswith(b"\n"):
                                buffer = line
                                break
                            cursor += len(line)
                            raw = line.decode("utf-8", errors="replace").rstrip("\r\n")
                            event = _parse_event_line(raw)
                            if event is None:
                                continue
                            event_name = str(event.get("event") or "message")
                            yield _build_event(raw, event=event_name, event_id=cursor)
                            if event.get("event") in stop_events:
                                return
                        continue

                    try:
                        stat = path.stat()
                    except FileNotFoundError:
                        buffer = b""
                        break

                    if (stat.st_dev, stat.st_ino) != file_id:
                        cursor = 0
                        buffer = b""
                        break

                    if stat.st_size < cursor:
                        cursor = stat.st_size
                        buffer = b""
                        handle.seek(cursor)

                    now = time.monotonic()
                    if now - last_ping >= ping_interval:
                        yield sse_text("ping", "keep-alive")
                        last_ping = now

                    await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
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
