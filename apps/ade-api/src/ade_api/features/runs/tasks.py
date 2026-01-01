"""Background task entrypoints for run queue backfills."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from ade_api.common.logging import log_context
from ade_api.db import db

logger = logging.getLogger(__name__)


async def enqueue_pending_runs_background(
    *,
    workspace_id: UUID,
    configuration_id: UUID,
    settings_payload: dict[str, Any],
) -> None:
    """Queue runs for uploaded documents after configuration activation."""

    from ade_api.features.configs.storage import ConfigStorage
    from ade_api.features.runs.event_stream import get_run_event_streams
    from ade_api.features.runs.service import RunsService
    from ade_api.features.system_settings.service import SafeModeService
    from ade_api.settings import Settings

    settings = Settings(**settings_payload)
    session_factory = db.sessionmaker
    storage = ConfigStorage(settings=settings)
    event_streams = get_run_event_streams()

    async with session_factory() as session:
        service = RunsService(
            session=session,
            settings=settings,
            safe_mode_service=SafeModeService(session=session, settings=settings),
            storage=storage,
            event_streams=event_streams,
            build_event_streams=event_streams,
        )
        try:
            count = await service.enqueue_pending_runs_for_configuration(
                configuration_id=configuration_id,
            )
            if count:
                logger.info(
                    "run.pending.enqueue.background.completed",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        count=count,
                    ),
                )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "run.pending.enqueue.background.failed",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                ),
            )
