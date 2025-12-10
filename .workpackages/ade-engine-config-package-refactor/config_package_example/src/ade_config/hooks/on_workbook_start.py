from __future__ import annotations

from typing import Any

from ade_engine.registry import hook


@hook("on_workbook_start")
def run(*, run_ctx: Any, logger: Any | None = None, **_: Any) -> None:
    # Example: seed shared state for the run.
    run_ctx.state.setdefault("notes", [])
    if logger:
        logger.info("Config hook: workbook start (%s)", getattr(run_ctx, "source_path", ""))
