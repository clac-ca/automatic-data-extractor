"""
Example: `on_run_end` hook

This hook runs ONCE after the entire pipeline has completed,
regardless of success or failure.

By the time this executes:
    • Extraction, mapping, normalization, and saving are all finished
    • Tables and workbook have already been written to disk (if successful)
    • `result` contains the run outcome and output file paths

Common use cases:
    • Logging / audit records
    • Sending notifications (Slack, email, webhooks)
    • Emitting telemetry / metrics
    • Cleanup tasks (temp files, state flags)
    • Post-run diagnostics

This hook does *not* modify tables, workbook, or result.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    run: Any | None = None,
    result: Any | None = None,
    logger=None,
    event_emitter=None,
    state: dict[str, Any] | None = None,
    file_names: tuple[str, ...] | None = None,
    manifest: Any | None = None,
    tables: list[Any] | None = None,
    workbook: Any | None = None,
    stage: Any | None = None,
    **_: Any,
) -> None:
    """
    Main entrypoint for the `on_run_end` hook.

    This hook cannot influence the pipeline. It is a final
    "after everything" callback for logging and notification.
    """

    # If key objects are missing, silently skip (common during failures)
    if logger is None or run is None or result is None:
        return

    # Extract run metadata safely
    run_id = getattr(run, "run_id", None)
    status = getattr(result, "status", None)
    output_paths = getattr(result, "output_paths", ()) or ()

    # -----------------------------------------------------------------------
    # EXAMPLE: Log final run status
    # -----------------------------------------------------------------------
    logger.info(
        "on_run_end: run_id=%s finished status=%s outputs=%s",
        run_id,
        status,
        [str(p) for p in output_paths],
    )

    # -----------------------------------------------------------------------
    # EXAMPLE: Emit a custom event to the frontend/monitoring system
    # -----------------------------------------------------------------------
    # if event_emitter is not None:
    #     event_emitter.custom(
    #         "hook.run_completed",
    #         stage=getattr(stage, "value", stage),
    #         run_id=str(run_id),
    #         status=str(status),
    #         outputs=[str(p) for p in output_paths],
    #     )
