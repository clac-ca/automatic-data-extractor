"""No-op sandbox hook."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.types.contexts import RunContext

def run(
    *,
    run_ctx: RunContext | None = None,
    logger: Logger | None = None,
    **_: Any,
) -> None:
    """Pass through with no side effects."""

    return None
