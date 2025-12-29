"""Background worker pool for queued ADE runs."""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ade_api.common.logging import log_context
from ade_api.features.runs.event_stream import RunEventStreamRegistry
from ade_api.features.runs.service import RunsService
from ade_api.features.system_settings.service import SafeModeService
from ade_api.settings import Settings

logger = logging.getLogger(__name__)


class RunWorkerPool:
    """Run workers that claim queued runs and execute them with bounded concurrency."""

    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_streams: RunEventStreamRegistry,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._event_streams = event_streams
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._poll_interval = 0.5
        self._cleanup_interval = 30.0

    async def start(self) -> None:
        if self._tasks:
            return
        for idx in range(self._settings.max_concurrency):
            self._tasks.append(asyncio.create_task(self._worker_loop(idx)))

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _worker_loop(self, worker_id: int) -> None:
        logger.info(
            "run.worker.start",
            extra=log_context(worker_id=worker_id),
        )
        last_cleanup = 0.0
        while not self._stop.is_set():
            should_sleep = False
            try:
                async with self._session_factory() as session:
                    service = self._build_service(session)
                    now = time.monotonic()
                    if now - last_cleanup >= self._cleanup_interval:
                        await service.expire_stuck_runs()
                        await service.expire_stuck_builds()
                        last_cleanup = now

                    run = await service.claim_next_run()
                    if run is None:
                        should_sleep = True
                    else:
                        options = await service.load_run_options(run)
                        await service.run_to_completion(run_id=run.id, options=options)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    "run.worker.loop.error",
                    extra=log_context(worker_id=worker_id),
                )
                should_sleep = True

            if should_sleep:
                await asyncio.sleep(self._poll_interval)

        logger.info(
            "run.worker.stop",
            extra=log_context(worker_id=worker_id),
        )

    def _build_service(self, session: AsyncSession) -> RunsService:
        return RunsService(
            session=session,
            settings=self._settings,
            safe_mode_service=SafeModeService(session=session, settings=self._settings),
            event_streams=self._event_streams,
            build_event_streams=self._event_streams,
        )


__all__ = ["RunWorkerPool"]
