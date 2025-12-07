"""No-op `on_run_start` hook."""

from __future__ import annotations

from logging import Logger
from typing import Any

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import RunContext
from ade_engine.infra.event_emitter import ConfigEventEmitter

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    run: RunContext | None = None,
    state: dict[str, Any] | None = None,  # shared dict for all hooks
    input_file_name: str | None = None,  # source file (if known)
    manifest: ManifestContext | None = None,
    logger: Logger | None = None,
    event_emitter: ConfigEventEmitter | None = None,
    **_: Any,
) -> None:
    """Pass through with no side effects."""
