"""on_run_start hook.

Runs once at the very beginning of a run, after the manifest and
telemetry have been initialized but before any IO happens.
"""

from typing import Any


def run(
    *,
    run: Any | None = None,          # RunContext: run_id, metadata, etc.
    state: dict[str, Any] | None = None,  # shared per-run dict
    manifest: Any | None = None,     # manifest context
    logger: Any | None = None,       # PipelineLogger
    stage: Any | None = None,        # e.g. 'on_run_start'
    **_: Any,
) -> None:
    """
    on_run_start: log high-level run info and initialize shared state.

    This hook does not change pipeline objects; it just mutates `state`
    and emits telemetry. It returns None.
    """
    if logger is None or run is None:
        return

    run_id = getattr(run, "run_id", None)
    metadata = getattr(run, "metadata", {}) or {}

    # Example: stash something in state for later hooks/detectors.
    if state is not None:
        state["run_id"] = run_id

    logger.note(
        "Run started",
        run_id=run_id,
        metadata=metadata,
        stage=stage,
    )
