"""Simple hook to leave a note in sandbox artifacts."""

from __future__ import annotations

from typing import Any


def run(*, logger: Any, **_: Any) -> None:
    """Emit a note so sandbox runs show hook wiring."""
    logger.note(message="Sandbox on_run_start hook executed.")
