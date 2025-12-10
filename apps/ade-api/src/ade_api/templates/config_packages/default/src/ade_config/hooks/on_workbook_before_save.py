from __future__ import annotations

from typing import Any

from ade_engine.registry import HookContext, HookName, hook


@hook(HookName.ON_WORKBOOK_BEFORE_SAVE)
def on_workbook_before_save(ctx: HookContext) -> None:
    """Example finalization hook."""

    if ctx.logger:
        ctx.logger.info("Config hook: workbook before save (%s)", ctx.run_metadata.get("output_file", ""))
