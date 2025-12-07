"""No-op `on_before_save` hook — returns the workbook unchanged."""

from __future__ import annotations

from logging import Logger
from typing import Any

from openpyxl import Workbook

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import NormalizedTable, RunContext, RunResult
from ade_engine.infra.event_emitter import ConfigEventEmitter

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    workbook: Workbook | None = None,
    tables: list[NormalizedTable] | None = None,
    run: RunContext | None = None,
    input_file_name: str | None = None,
    manifest: ManifestContext | None = None,
    state: dict[str, Any] | None = None,
    logger: Logger | None = None,
    event_emitter: ConfigEventEmitter | None = None,
    result: RunResult | None = None,
    **_: Any,
) -> Workbook | None:
    """Pass through workbook without modification."""

    return workbook
