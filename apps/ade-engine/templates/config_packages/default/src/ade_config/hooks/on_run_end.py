"""No-op `on_run_end` hook."""

from __future__ import annotations

from logging import Logger
from typing import Any

from openpyxl import Workbook

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import ExtractedTable, MappedTable, NormalizedTable, RunContext, RunResult
from ade_engine.infra.event_emitter import ConfigEventEmitter

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    run: RunContext | None = None,
    result: RunResult | None = None,
    logger: Logger | None = None,
    event_emitter: ConfigEventEmitter | None = None,
    state: dict[str, Any] | None = None,
    input_file_name: str | None = None,
    manifest: ManifestContext | None = None,
    tables: list[ExtractedTable | MappedTable | NormalizedTable] | None = None,
    workbook: Workbook | None = None,
    **_: Any,
) -> None:
    """Pass through with no side effects."""

    return None
