"""Final hook before saving the output workbook."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.types.contexts import RunContext


def run(
    *,
    run_ctx: RunContext,
    logger: Logger | None = None,
    **_: Any,
) -> None:
    return None
