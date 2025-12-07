"""Inspect extracted tables before mapping."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.types.contexts import RunContext, TableContext


def run(
    *,
    table_ctx: TableContext,
    run_ctx: RunContext,
    logger: Logger | None = None,
    **_: Any,
) -> None:
    return None
