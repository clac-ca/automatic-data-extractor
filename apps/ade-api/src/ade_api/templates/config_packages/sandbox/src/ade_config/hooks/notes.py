"""Tiny hook used during sandbox runs to emit a note event."""

from __future__ import annotations

from typing import Any


def run(
    *,
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    manifest: Any | None = None,
    tables: list[Any] | None = None,
    logger: Any,
    event_emitter: Any,
    **_: Any,
) -> None:
    """Emit a simple note so sandbox runs have observable hook output."""

    run_id = getattr(run, "run_id", None) or "sandbox"
    logger.info("sandbox hook run_id=%s tables=%d", run_id, len(tables or []))
    event_emitter.custom("hook.note", status="ok", run_id=str(run_id))
