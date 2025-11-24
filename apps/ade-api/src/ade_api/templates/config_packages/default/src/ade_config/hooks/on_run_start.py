"""on_run_start hook.

Runs once at the very beginning of a run, after the manifest and
telemetry have been initialized but before any IO happens.
"""

from __future__ import annotations

from typing import Any


def run(ctx: Any) -> None:
    """
    `ctx` is a HookContext provided by ade_engine.

    Here we just log a small note with the run_id and any metadata that
    the caller passed in.
    """
    logger = getattr(ctx, "logger", None)
    run = getattr(ctx, "run", None)

    if logger is None or run is None:
        return

    run_id = getattr(run, "run_id", None)
    metadata = getattr(run, "metadata", {})

    logger.note(
        "Run started",
        run_id=run_id,
        metadata=metadata,
        stage=getattr(ctx, "stage", None),
    )
