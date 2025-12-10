from __future__ import annotations

from ade_engine.registry.models import HookContext, HookName


def register(registry):
    registry.register_hook(on_sheet_start, hook_name=HookName.ON_SHEET_START, priority=0)


def on_sheet_start(ctx: HookContext) -> None:
    """Example sheet-start hook."""

    sheet_name = getattr(ctx.sheet, "title", getattr(ctx.sheet, "name", ""))
    if ctx.logger:
        ctx.logger.info("Config hook: sheet start (%s)", sheet_name)
