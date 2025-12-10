from __future__ import annotations

from typing import Any

from ade_engine.registry import HookContext, HookName, hook


@hook(HookName.ON_WORKBOOK_START)
def on_workbook_start(ctx: HookContext) -> None:
    """Seed shared run state."""

    ctx.state.setdefault("notes", [])
    if ctx.logger:
        ctx.logger.info("Config hook: workbook start (%s)", ctx.run_metadata.get("input_file", ""))
