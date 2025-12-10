from __future__ import annotations

from typing import Any

from ade_engine.registry import HookContext, HookName, hook


@hook(HookName.ON_WORKBOOK_START)
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
