"""Background task entrypoints for build execution."""

from __future__ import annotations

import logging
from typing import Any

from ade_api.common.logging import log_context
from ade_api.db.session import get_sessionmaker

logger = logging.getLogger(__name__)


async def execute_build_background(
    context_data: dict[str, Any],
    options_data: dict[str, Any],
    settings_payload: dict[str, Any],
) -> None:
    """Run a build in the background using a fresh DB session."""

    from ade_api.features.configs.storage import ConfigStorage
    from ade_api.features.runs.event_stream import get_run_event_streams
    from ade_api.settings import Settings

    from .schemas import BuildCreateOptions
    from .service import BuildExecutionContext, BuildsService

    settings = Settings(**settings_payload)
    session_factory = get_sessionmaker(settings=settings)
    storage = ConfigStorage(settings=settings)
    event_streams = get_run_event_streams()
    context = BuildExecutionContext.from_dict(context_data)
    options = BuildCreateOptions(**options_data)
    async with session_factory() as session:
        service = BuildsService(
            session=session,
            settings=settings,
            storage=storage,
            event_streams=event_streams,
        )
        try:
            await service.run_to_completion(context=context, options=options)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "build.background.failed",
                extra=log_context(
                    workspace_id=context.workspace_id,
                    configuration_id=context.configuration_id,
                    build_id=context.build_id,
                ),
            )
