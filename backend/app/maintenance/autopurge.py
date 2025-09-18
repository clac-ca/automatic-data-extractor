"""Automatic scheduling for document purge runs."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from .. import config
from ..db import get_sessionmaker
from ..services.documents import purge_expired_documents
from ..services.maintenance_status import (
    record_auto_purge_failure,
    record_auto_purge_success,
)

logger = logging.getLogger(__name__)


class AutoPurgeScheduler:
    """Manage the background task that purges expired documents."""

    def __init__(self) -> None:
        settings = config.get_settings()
        self._enabled = settings.purge_schedule_enabled
        self._interval = settings.purge_schedule_interval_seconds
        self._run_on_startup = settings.purge_schedule_run_on_startup
        self._session_factory = get_sessionmaker()
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        """Spawn the background purge loop when enabled."""

        if not self._enabled:
            logger.info("Automatic document purge disabled via configuration")
            return

        if self._interval <= 0:
            logger.warning(
                "Automatic document purge interval must be positive; scheduler will not start",
            )
            return

        if self._task is not None:
            return

        self._stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())

    async def stop(self) -> None:
        """Signal the background loop to exit and wait for completion."""

        if self._task is None or self._stop_event is None:
            return

        self._stop_event.set()
        task = self._task
        try:
            await task
        finally:
            self._task = None
            self._stop_event = None

    async def _run(self) -> None:
        assert self._stop_event is not None

        try:
            if self._run_on_startup:
                await self._purge_once()

            while True:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._interval
                    )
                    break
                except asyncio.TimeoutError:
                    await self._purge_once()
        except asyncio.CancelledError:  # pragma: no cover - propagation
            raise
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Automatic purge scheduler encountered an error")
        finally:
            self._task = None

    async def _purge_once(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._purge_once_sync)

    def _purge_once_sync(self) -> None:
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._session_factory() as db_session:
                summary = purge_expired_documents(
                    db_session,
                    audit_source="scheduler",
                    audit_request_id=started_at,
                )
                completed_at = datetime.now(timezone.utc).isoformat()
                record_auto_purge_success(
                    db_session,
                    summary=summary,
                    started_at=started_at,
                    completed_at=completed_at,
                    interval_seconds=self._interval,
                )
                db_session.commit()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Automatic purge run failed")
            self._record_failure_status(started_at, exc)
            return

        logger.info(
            "Automatic purge run completed",
            extra={"summary": asdict(summary)},
        )

    def _record_failure_status(self, started_at: str, error: Exception) -> None:
        try:
            with self._session_factory() as db_session:
                record_auto_purge_failure(
                    db_session,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    interval_seconds=self._interval,
                    error=str(error),
                )
                db_session.commit()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Unable to persist automatic purge failure status")


__all__ = ["AutoPurgeScheduler"]

