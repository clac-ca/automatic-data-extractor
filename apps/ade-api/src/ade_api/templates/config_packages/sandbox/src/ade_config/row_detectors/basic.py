"""Simple row detectors mirroring ade_engine fixture behavior."""

from __future__ import annotations


def detect_header(
    *,
    row_index: int,
    input_file_name: str | None = None,
    manifest=None,
    logger=None,
    event_emitter=None,
    **_: object,
) -> dict[str, object]:
    """Score the first row as the header and others as data."""
    return {"scores": {"header": 1.0 if row_index == 1 else 0.0, "data": 0.0}}


def detect_data(
    *,
    row_index: int,
    input_file_name: str | None = None,
    manifest=None,
    logger=None,
    event_emitter=None,
    **_: object,
) -> dict[str, object]:
    """Score rows after the header as data rows."""
    return {"scores": {"header": 0.0, "data": 1.0 if row_index > 1 else 0.0}}
