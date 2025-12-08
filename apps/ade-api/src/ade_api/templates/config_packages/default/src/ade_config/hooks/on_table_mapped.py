"""Optional mapping patch hook (LLM/manual overrides)."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.types.contexts import RunContext, TableContext
from ade_engine.types.mapping import ColumnMappingPatch


def run(
    *,
    table_ctx: TableContext,
    run_ctx: RunContext,
    logger: Logger | None = None,
    **_: Any,
) -> ColumnMappingPatch | None:
    return None
