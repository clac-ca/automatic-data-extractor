"""No-op `on_after_extract` hook — returns the table unchanged."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import ExtractedTable, RunContext
from ade_engine.infra.event_emitter import ConfigEventEmitter

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    table: ExtractedTable | None = None,
    run: RunContext | None = None,
    state: dict[str, Any] | None = None,
    input_file_name: str | None = None,
    manifest: ManifestContext | None = None,
    logger: Logger | None = None,
    event_emitter: ConfigEventEmitter | None = None,
    **_: Any,
) -> ExtractedTable | None:
    """Pass through the table without modification."""

    return table
