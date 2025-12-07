"""Example hook: configure each output worksheet before tables are written."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.types.contexts import RunContext, WorksheetContext


def run(
    *,
    sheet_ctx: WorksheetContext,
    run_ctx: RunContext,
    logger: Logger | None = None,
    **_: Any,
) -> None:
    return None
