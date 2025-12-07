"""No-op `on_after_mapping` hook — returns the mapped table unchanged."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import MappedTable, RunContext
from ade_engine.infra.event_emitter import ConfigEventEmitter

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    table: MappedTable | None = None,
    run: RunContext | None = None,
    state: dict[str, Any] | None = None,
    input_file_name: str | None = None,
    manifest: ManifestContext | None = None,
    logger: Logger | None = None,
    event_emitter: ConfigEventEmitter | None = None,
    **_: Any,
) -> MappedTable | None:
    """Pass through the mapped table without modification."""

    return table
