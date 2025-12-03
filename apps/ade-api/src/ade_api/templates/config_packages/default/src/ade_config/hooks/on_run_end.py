"""on_run_end hook.

Runs once after the run is complete (success or failure).
"""

from typing import Any


def run(
    *,
    run: Any | None = None,
    result: Any | None = None,
    logger=None,
    event_emitter=None,
    state: dict[str, Any] | None = None,
    manifest: Any | None = None,
    tables: list[Any] | None = None,
    workbook: Any | None = None,
    stage: Any | None = None,
    **_: Any,
) -> None:
    """
    on_run_end: log final status; no pipeline changes.

    This hook does not change tables/workbook/result.
    """
    if logger is None or run is None or result is None:
        return

    run_id = getattr(run, "run_id", None)
    status = getattr(result, "status", None)
    output_paths = getattr(result, "output_paths", ()) or ()

    logger.info("Run finished status=%s outputs=%s", status, [str(p) for p in output_paths])
    if event_emitter is not None:
        event_emitter.custom(
            "hook.completed",
            stage=getattr(stage, "value", stage),
            run_id=str(run_id),
            status=str(status),
            outputs=[str(p) for p in output_paths],
        )
