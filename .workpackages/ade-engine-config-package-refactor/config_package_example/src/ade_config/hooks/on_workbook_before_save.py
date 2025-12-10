from __future__ import annotations

from ade_engine.registry.models import HookContext, HookName


def register(registry):
    registry.register_hook(on_workbook_before_save, hook_name=HookName.ON_WORKBOOK_BEFORE_SAVE, priority=0)


def on_workbook_before_save(ctx: HookContext) -> None:
    """Example finalization hook."""

    if ctx.logger:
        ctx.logger.info("Config hook: workbook before save (%s)", ctx.run_metadata.get("output_file", ""))
