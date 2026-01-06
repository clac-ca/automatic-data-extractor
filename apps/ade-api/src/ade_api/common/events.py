from __future__ import annotations

from typing import Any

EventRecord = dict[str, Any]


def strip_sequence(event: EventRecord) -> EventRecord:
    """Return a copy of ``event`` without ``sequence``.

    SSE already provides a monotonic `id:`; removing `sequence` from the JSON payload
    keeps the envelope closer to the engine format and avoids duplication.
    """

    if "sequence" not in event:
        return event
    stripped = dict(event)
    stripped.pop("sequence", None)
    return stripped
