from __future__ import annotations

from typing import Any

EventRecord = dict[str, Any]


def strip_sequence(event: EventRecord) -> EventRecord:
    """Return a copy of ``event`` without ``sequence``.

    Use when sequence metadata is carried out-of-band and you want the payload unchanged.
    """

    if "sequence" not in event:
        return event
    stripped = dict(event)
    stripped.pop("sequence", None)
    return stripped
