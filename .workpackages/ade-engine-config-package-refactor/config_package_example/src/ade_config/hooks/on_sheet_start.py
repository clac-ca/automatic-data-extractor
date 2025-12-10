from __future__ import annotations

from typing import Any

from ade_engine.registry import hook


@hook("on_sheet_start")
def run(*, sheet_ctx: Any, run_ctx: Any, logger: Any | None = None, **_: Any) -> None:
    # Example: skip or tag sheets.
    if logger:
        logger.info("Config hook: sheet start (%s)", getattr(sheet_ctx, "name", ""))
