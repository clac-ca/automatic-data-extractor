from __future__ import annotations

from typing import Any

from ade_engine.registry import HookContext, HookName, hook


@hook(HookName.ON_WORKBOOK_BEFORE_SAVE)
def on_workbook_before_save(
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
    """Example finalization hook."""

    if logger:
        logger.info("Config hook: workbook before save (%s)", metadata.get("output_file", ""))
