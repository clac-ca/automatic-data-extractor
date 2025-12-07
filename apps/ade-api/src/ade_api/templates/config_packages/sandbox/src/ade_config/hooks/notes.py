"""No-op sandbox hook."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import ExtractedTable, MappedTable, NormalizedTable, RunContext
from ade_engine.infra.event_emitter import ConfigEventEmitter


def run(
    *,
    run: RunContext | None = None,
    state: dict[str, Any] | None = None,
    manifest: ManifestContext | None = None,
    tables: list[ExtractedTable | MappedTable | NormalizedTable] | None = None,
    logger: Logger | None = None,
    event_emitter: ConfigEventEmitter | None = None,
    **_: Any,
) -> None:
    """Pass through with no side effects."""

    return None
