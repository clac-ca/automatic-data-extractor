from __future__ import annotations

from ade_engine.registry.models import HookContext, HookName


def register(registry):
    registry.register_hook(on_workbook_start, hook_name=HookName.ON_WORKBOOK_START, priority=0)


def on_workbook_start(
    *,
    hook_name,
    metadata,
    state,
    workbook,
    sheet,
    table,
    input_file_name,
    logger,
) -> None:
    """Seed shared run state."""

    state.setdefault("notes", [])
    if logger:
        logger.info("Config hook: workbook start (%s)", metadata.get("input_file", ""))
