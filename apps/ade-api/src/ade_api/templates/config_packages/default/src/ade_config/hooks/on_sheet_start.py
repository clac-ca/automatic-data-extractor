from __future__ import annotations

from typing import Any

from ade_engine.registry import HookContext, HookName, hook


@hook(HookName.ON_SHEET_START)
def on_sheet_start(ctx: HookContext) -> None:
    """Example sheet-start hook."""

    sheet_name = getattr(ctx.sheet, "title", getattr(ctx.sheet, "name", ""))
    if ctx.logger:
        ctx.logger.info("Config hook: sheet start (%s)", sheet_name)
