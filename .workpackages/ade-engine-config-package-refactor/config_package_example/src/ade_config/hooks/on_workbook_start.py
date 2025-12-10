from __future__ import annotations

from ade_engine.registry.models import HookContext, HookName


def register(registry):
    registry.register_hook(on_workbook_start, hook_name=HookName.ON_WORKBOOK_START, priority=0)


def on_workbook_start(ctx: HookContext) -> None:
    """Seed shared run state."""

    ctx.state.setdefault("notes", [])
    if ctx.logger:
        ctx.logger.info("Config hook: workbook start (%s)", ctx.run_metadata.get("input_file", ""))
