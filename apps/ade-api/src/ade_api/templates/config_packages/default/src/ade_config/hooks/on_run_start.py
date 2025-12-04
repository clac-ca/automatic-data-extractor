"""
Example: `on_run_start` hook

This hook runs ONCE at the very beginning of a pipeline run,
right after the manifest and telemetry have been initialized,
but BEFORE any I/O or extraction occurs.

This makes it an ideal place to:
    • Log the start of the run
    • Initialize per-run shared state
    • Emit analytics or monitoring events
    • Stamp run metadata (timestamps, version info, etc.)
    • Perform lightweight validation of manifest or configuration

No data has been extracted yet — this is a purely administrative checkpoint.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    run: Any | None = None,            # RunContext: run_id, metadata, etc.
    state: dict[str, Any] | None = None,  # shared dict for all hooks
    input_file_name: str | None = None,  # source file (if known)
    manifest: Any | None = None,       # manifest context for this run
    logger=None,                       # logging.Logger instance
    event_emitter=None,                # EventEmitter instance
    stage: Any | None = None,          # stage identifier (e.g., 'on_run_start')
    **_: Any,
) -> None:
    """
    Main entrypoint for the `on_run_start` hook.

    This hook is NOT allowed to modify tables (none exist yet),
    nor can it alter the run context. It is strictly for initialization,
    logging, and emitting structured events.
    """

    # If key components are missing, do nothing
    if logger is None or run is None or event_emitter is None:
        return

    run_id = getattr(run, "run_id", None)
    metadata = getattr(run, "metadata", {}) or {}

    # -----------------------------------------------------------------------
    # EXAMPLE: Initialize shared state for later hooks
    # -----------------------------------------------------------------------
    #
    # The `state` dictionary persists across the entire run and can pass
    # information from here to later hooks such as on_after_extract,
    # on_after_mapping, on_before_save, etc.
    # -----------------------------------------------------------------------
    if state is not None:
        state["run_id"] = run_id
        # You could also set timestamps, counters, or other reusable flags:
        # state["start_timestamp"] = time.time()

    # -----------------------------------------------------------------------
    # EXAMPLE: Human-friendly log entry
    # -----------------------------------------------------------------------
    logger.info(
        "on_run_start: beginning run run_id=%s (stage=%s)",
        run_id,
        getattr(stage, "value", stage),
    )
    logger.debug("on_run_start: metadata=%s", metadata)

    # -----------------------------------------------------------------------
    # EXAMPLE: Emit a custom event to the frontend/monitoring system
    # -----------------------------------------------------------------------
    # event_emitter.custom(
    #     "hook.run_started",
    #     stage=getattr(stage, "value", stage),
    #     run_id=str(run_id),
    #     metadata=metadata,
    # )
