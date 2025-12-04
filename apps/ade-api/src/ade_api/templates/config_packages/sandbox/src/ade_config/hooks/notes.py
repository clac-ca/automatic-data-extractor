"""Simple hook to leave a note in sandbox artifacts."""

from __future__ import annotations

from typing import Any


def run(*, logger: Any, event_emitter: Any, **_: Any) -> None:
    """Emit a note so sandbox runs show hook wiring."""
    logger.info("Sandbox on_run_start hook executed.")
    event_emitter.custom("hook.sandbox.note", status="ok")
