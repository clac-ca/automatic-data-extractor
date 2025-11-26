"""on_run_end hook.

Runs once after the run is complete (success or failure).
"""

from __future__ import annotations

from typing import Any


def run(ctx: Any) -> None:
    """
    Emit a simple run summary.

    This uses the PipelineLogger (ctx.logger) so the message shows up in
    telemetry events.
    """
    logger = getattr(ctx, "logger", None)
    run = getattr(ctx, "run", None)
    result = getattr(ctx, "result", None)

    if logger is None or run is None or result is None:
        return

    run_id = getattr(run, "run_id", None)
    status = getattr(result, "status", None)
    output_paths = getattr(result, "output_paths", ()) or ()

    logger.note(
        "Run finished",
        stage=getattr(ctx, "stage", None),
        run_id=run_id,
        status=status,
        outputs=[str(p) for p in output_paths],
    )
