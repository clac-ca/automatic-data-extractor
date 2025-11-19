"""Example on_job_start hook."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def run(*, job_id: str | None = None, note=None, **_: Any) -> None:
    """Record a log entry in the artifact noting when execution began."""

    if note is not None:
        message = (
            f"Job {job_id or 'unknown'} started at "
            f"{datetime.now(tz=UTC).isoformat()}"
        )
        note("job_start", message)
