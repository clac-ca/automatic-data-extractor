"""Run orchestration service coordinating DB state and engine execution."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.events import (
    EventRecord,
    coerce_event_record,
    new_event_record,
)
from ade_api.common.logging import log_context
from ade_api.common.pagination import Page
from ade_api.common.time import utc_now
from ade_api.common.types import OrderBy
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.documents.repository import DocumentsRepository
from ade_api.features.documents.staging import stage_document_input
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.workspaces.repository import WorkspacesRepository
from ade_api.features.workspaces.settings import read_processing_paused
from ade_api.features.runs.event_stream import (
    RunEventContext,
    RunEventStream,
    RunEventStreamRegistry,
)
from ade_api.features.system_settings.schemas import SafeModeStatus
from ade_api.features.system_settings.service import (
    SAFE_MODE_DEFAULT_DETAIL,
    SafeModeService,
)
from ade_api.infra.storage import (
    workspace_documents_root,
    workspace_run_root,
)
from ade_api.infra.venv import apply_venv_to_env, venv_python_path
from ade_api.models import (
    Build,
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentStatus,
    Run,
    RunField,
    RunMetrics,
    RunStatus,
    RunTableColumn,
)
from ade_api.features.documents.schemas import DocumentOut
from ade_api.settings import Settings

from .exceptions import (
    RunDocumentMissingError,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunOutputNotReadyError,
    RunQueueFullError,
)
from .filters import RunColumnFilters, RunFilters
from .repository import RunsRepository
from .runner import EngineSubprocessRunner, StdoutFrame
from .schemas import (
    RunBatchCreateOptions,
    RunCreateOptions,
    RunCreateOptionsBase,
    RunInput,
    RunLinks,
    RunOutput,
    RunResource,
)
from .supervisor import RunExecutionSupervisor

__all__ = [
    "RunExecutionContext",
    "RunInputMissingError",
    "RunDocumentMissingError",
    "RunLogsFileMissingError",
    "RunNotFoundError",
    "RunOutputNotReadyError",
    "RunOutputMissingError",
    "RunsService",
    "RunStreamFrame",
]

logger = logging.getLogger(__name__)
event_logger = logging.getLogger("ade_api.runs.events")

DEFAULT_EVENTS_PAGE_LIMIT = 1000
DEFAULT_REQUEUE_DELAY_SECONDS = 5
DEFAULT_BACKOFF_BASE_SECONDS = 1
DEFAULT_BACKOFF_MAX_SECONDS = 60


# Stream frames include engine output frames consumed internally plus
# EventRecords surfaced to callers alongside RunExecutionResult markers used to
# finalize runs.
@dataclass(slots=True)
class RunExecutionResult:
    """Outcome of an engine-backed run execution."""

    status: RunStatus
    return_code: int | None
    paths_snapshot: RunPathsSnapshot
    error_message: str | None = None


RunStreamFrame = StdoutFrame | EventRecord | RunExecutionResult


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RunPathsSnapshot:
    """Container for run-relative output and log paths.

    This is the normalized view that higher layers use. All paths here are
    relative to the runs root, so they are safe to surface externally.
    """

    events_path: str | None = None
    output_path: str | None = None
    processed_file: str | None = None


@dataclass(slots=True, frozen=True)
class RunExecutionContext:
    """Minimal identifiers required to execute a run."""

    run_id: UUID
    configuration_id: UUID
    workspace_id: UUID
    build_id: UUID


# --------------------------------------------------------------------------- #
# Main service
# --------------------------------------------------------------------------- #


class RunsService:
    """Coordinate run persistence, execution, and serialization for the API.

    Responsibilities:
    - create and persist Run rows
    - ensure the configuration environment is built
    - stage input documents and invoke the engine
    - stream ADE events for live runs
    - resolve artifacts and summaries after completion
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        supervisor: RunExecutionSupervisor | None = None,
        safe_mode_service: SafeModeService | None = None,
        storage: ConfigStorage | None = None,
        event_streams: RunEventStreamRegistry | None = None,
        build_event_streams: RunEventStreamRegistry | None = None,
    ) -> None:
        from ade_api.features.builds.service import BuildsService
        from ade_api.features.documents.change_feed import DocumentChangesService
        from ade_api.features.documents.service import DocumentsService

        self._session = session
        self._settings = settings
        self._configs = ConfigurationsRepository(session)
        self._runs = RunsRepository(session)
        self._supervisor = supervisor or RunExecutionSupervisor()
        self._documents = DocumentsRepository(session)
        self._workspaces = WorkspacesRepository(session)
        self._safe_mode_service = safe_mode_service
        self._storage = storage or ConfigStorage(
            settings=settings,
        )
        self._event_streams = event_streams or RunEventStreamRegistry()
        self._build_event_streams = build_event_streams or self._event_streams
        self._builds_service = BuildsService(
            session=session,
            settings=settings,
            storage=self._storage,
            event_streams=self._build_event_streams,
        )
        self._document_changes = DocumentChangesService(session=session, settings=settings)
        self._documents_service = DocumentsService(session=session, settings=settings)

        if settings.documents_dir is None:
            raise RuntimeError("ADE_DOCUMENTS_DIR is not configured")
        if settings.runs_dir is None:
            raise RuntimeError("ADE_RUNS_DIR is not configured")

        self._runs_dir = Path(settings.runs_dir)
        lease_seconds = int(settings.run_lease_seconds)
        if settings.run_timeout_seconds:
            lease_seconds = max(lease_seconds, int(settings.run_timeout_seconds))
        self._run_lease_seconds = lease_seconds
        self._run_max_attempts = int(settings.run_max_attempts)

    # --------------------------------------------------------------------- #
    # Run lifecycle: creation and execution
    # --------------------------------------------------------------------- #

    async def prepare_run(
        self,
        *,
        configuration_id: UUID,
        options: RunCreateOptions,
    ) -> Run:
        """Create the queued run row and persist initial events."""

        logger.debug(
            "run.prepare.start",
            extra=log_context(
                configuration_id=configuration_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
                force_rebuild=options.force_rebuild,
                input_document_id=options.input_document_id,
            ),
        )

        configuration = await self._resolve_configuration(configuration_id)

        input_document_id = options.input_document_id
        if not input_document_id:
            raise RunInputMissingError("Input document is required to create a run")
        await self._require_document(
            workspace_id=configuration.workspace_id,
            document_id=input_document_id,
        )

        existing = await self._runs.list_active_for_documents(
            configuration_id=configuration.id,
            document_ids=[input_document_id],
        )
        if existing:
            run = existing[0]
            configuration.last_used_at = utc_now()  # type: ignore[attr-defined]
            await self._session.commit()
            existing_options = await self.load_run_options(run)
            mode_literal = "validate" if existing_options.validate_only else "execute"
            await self._ensure_run_queued_event(
                run=run,
                mode_literal=mode_literal,
                options=existing_options,
            )
            logger.info(
                "run.prepare.noop",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    input_document_id=input_document_id,
                    status=run.status.value,
                ),
            )
            return run

        await self._enforce_queue_capacity()

        selected_sheet_names = self._select_input_sheet_names(options)
        run_options_payload = options.model_dump(mode="json", exclude_none=True)
        await self._insert_runs_for_documents(
            configuration=configuration,
            document_ids=[input_document_id],
            input_sheet_names_by_document_id={
                input_document_id: selected_sheet_names or None,
            },
            run_options_by_document_id={
                input_document_id: run_options_payload,
            },
            document_status=None,
            existing_statuses=[RunStatus.QUEUED, RunStatus.RUNNING],
        )

        # Touch configuration usage timestamp.
        configuration.last_used_at = utc_now()  # type: ignore[attr-defined]
        await self._session.commit()

        run = await self._require_active_run(
            configuration_id=configuration.id,
            document_id=input_document_id,
        )

        mode_literal = "validate" if options.validate_only else "execute"
        await self._emit_api_event(
            run=run,
            type_="run.queued",
            payload={
                "status": "queued",
                "mode": mode_literal,
                "options": run_options_payload,
            },
        )

        logger.info(
            "run.prepare.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                input_document_id=input_document_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
                force_rebuild=options.force_rebuild,
            ),
        )
        return run

    async def prepare_run_for_workspace(
        self,
        *,
        workspace_id: UUID,
        input_document_id: UUID,
        configuration_id: UUID | None,
        options: RunCreateOptionsBase | None = None,
    ) -> Run:
        """Create a run for the workspace, resolving the active configuration if needed."""

        configuration = await self._resolve_workspace_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        run_options = self._merge_run_options(
            input_document_id=input_document_id,
            options=options,
        )
        return await self.prepare_run(
            configuration_id=configuration.id,
            options=run_options,
        )

    async def prepare_runs_batch(
        self,
        *,
        configuration_id: UUID,
        document_ids: Sequence[UUID],
        options: RunBatchCreateOptions,
        input_sheet_names_by_document_id: dict[UUID, list[str]] | None = None,
        active_sheet_only_by_document_id: dict[UUID, bool] | None = None,
    ) -> list[Run]:
        """Create queued runs for each document id, enforcing all-or-nothing semantics."""

        logger.debug(
            "run.prepare.batch.start",
            extra=log_context(
                configuration_id=configuration_id,
                document_count=len(document_ids),
                validate_only=options.validate_only,
                dry_run=options.dry_run,
                force_rebuild=options.force_rebuild,
            ),
        )

        if not document_ids:
            return []

        configuration = await self._resolve_configuration(configuration_id)
        await self._require_documents(
            workspace_id=configuration.workspace_id,
            document_ids=document_ids,
        )

        batch_active_sheet_only = bool(getattr(options, "active_sheet_only", False))
        normalized_sheet_names: dict[UUID, list[str] | None] = {}
        active_sheet_only_lookup: dict[UUID, bool] = {}
        run_options_by_document_id: dict[UUID, RunCreateOptions] = {}

        existing = await self._runs.list_active_for_documents(
            configuration_id=configuration.id,
            document_ids=list(document_ids),
        )
        existing_ids = {run.input_document_id for run in existing}
        new_document_ids = [doc_id for doc_id in document_ids if doc_id not in existing_ids]

        if new_document_ids:
            await self._enforce_queue_capacity(requested=len(new_document_ids))

            for document_id in new_document_ids:
                input_sheet_names = None
                if input_sheet_names_by_document_id and document_id in input_sheet_names_by_document_id:
                    raw_names = input_sheet_names_by_document_id.get(document_id) or []
                    normalized = self._select_input_sheet_names(
                        RunCreateOptions(input_document_id=document_id, input_sheet_names=raw_names),
                    )
                    input_sheet_names = normalized or None
                active_sheet_only = batch_active_sheet_only
                if active_sheet_only_by_document_id and document_id in active_sheet_only_by_document_id:
                    active_sheet_only = bool(active_sheet_only_by_document_id.get(document_id))
                if input_sheet_names:
                    active_sheet_only = False
                normalized_sheet_names[document_id] = input_sheet_names
                active_sheet_only_lookup[document_id] = active_sheet_only
                run_options_by_document_id[document_id] = RunCreateOptions(
                    dry_run=options.dry_run,
                    validate_only=options.validate_only,
                    force_rebuild=options.force_rebuild,
                    log_level=options.log_level,
                    input_document_id=document_id,
                    input_sheet_names=input_sheet_names,
                    active_sheet_only=active_sheet_only,
                    metadata=options.metadata,
                )

            await self._insert_runs_for_documents(
                configuration=configuration,
                document_ids=new_document_ids,
                input_sheet_names_by_document_id=normalized_sheet_names,
                run_options_by_document_id={
                    doc_id: run_options.model_dump(mode="json", exclude_none=True)
                    for doc_id, run_options in run_options_by_document_id.items()
                },
                document_status=None,
                existing_statuses=[RunStatus.QUEUED, RunStatus.RUNNING],
            )

        configuration.last_used_at = utc_now()  # type: ignore[attr-defined]
        await self._session.commit()

        runs = await self._runs.list_active_for_documents(
            configuration_id=configuration.id,
            document_ids=list(document_ids),
        )

        for run in runs:
            document_id = run.input_document_id
            run_options = run_options_by_document_id.get(document_id)
            if run_options is None:
                run_options = await self.load_run_options(run)
            mode_literal = "validate" if run_options.validate_only else "execute"
            await self._ensure_run_queued_event(
                run=run,
                mode_literal=mode_literal,
                options=run_options,
            )

        if runs:
            logger.info(
                "run.prepare.batch.success",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    count=len(runs),
                ),
            )
        return runs

    async def prepare_runs_batch_for_workspace(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        configuration_id: UUID | None,
        options: RunBatchCreateOptions,
    ) -> list[Run]:
        """Create batch runs for the workspace, resolving the active configuration if needed."""

        configuration = await self._resolve_workspace_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        return await self.prepare_runs_batch(
            configuration_id=configuration.id,
            document_ids=document_ids,
            options=options,
        )

    async def load_run_options(self, run: Run) -> RunCreateOptions:
        """Rehydrate run options from the run row."""

        payload: dict[str, Any] = dict(run.run_options or {})

        if "input_document_id" not in payload and run.input_document_id:
            payload["input_document_id"] = str(run.input_document_id)
        if "input_sheet_names" not in payload and run.input_sheet_names:
            payload["input_sheet_names"] = list(run.input_sheet_names)

        try:
            return RunCreateOptions(**payload)
        except Exception:
            logger.warning(
                "run.options.load.failed",
                extra=log_context(run_id=run.id),
            )
            return RunCreateOptions(
                input_document_id=str(run.input_document_id),
                input_sheet_names=list(run.input_sheet_names or []),
            )

    async def claim_next_run(self, *, worker_id: str) -> Run | None:
        now = utc_now()
        lease_expires_at = now + timedelta(seconds=self._run_lease_seconds)
        candidate = (
            select(Run.id)
            .where(
                Run.status == RunStatus.QUEUED,
                Run.available_at <= now,
                Run.attempt_count < Run.max_attempts,
            )
            .order_by(Run.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )
        # One statement claims a single queued run and sets a lease; races simply affect rowcount.
        stmt = (
            update(Run)
            .where(
                Run.id == candidate,
                Run.status == RunStatus.QUEUED,
            )
            .values(
                status=RunStatus.RUNNING,
                claimed_by=worker_id,
                claim_expires_at=lease_expires_at,
                started_at=now,
                attempt_count=Run.attempt_count + 1,
                error_message=None,
            )
            .returning(Run.id)
        )
        result = await self._session.execute(stmt)
        run_id = result.scalar_one_or_none()
        await self._session.commit()
        if run_id is None:
            return None
        return await self._require_run(run_id)

    async def enqueue_pending_runs_for_configuration(
        self,
        *,
        configuration_id: UUID,
        batch_size: int | None = None,
    ) -> int:
        """Queue runs for uploaded documents without runs using the active configuration."""

        try:
            configuration = await self._resolve_configuration(configuration_id)
        except ConfigurationNotFoundError:
            return 0
        if await self._processing_paused(configuration.workspace_id):
            logger.info(
                "run.pending.enqueue.skip.processing_paused",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                ),
            )
            return 0
        if configuration.status is not ConfigurationStatus.ACTIVE:
            logger.info(
                "run.pending.enqueue.skip.inactive_config",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    status=configuration.status.value,
                ),
            )
            return 0

        batch_size = batch_size or self._settings.queue_size or 100
        if batch_size <= 0:
            return 0

        total = 0
        while True:
            remaining = await self._remaining_queue_capacity()
            if remaining is not None and remaining <= 0:
                break
            limit = batch_size if remaining is None else min(batch_size, remaining)
            documents = await self._pending_documents(
                workspace_id=configuration.workspace_id,
                configuration_id=configuration.id,
                limit=limit,
            )
            if not documents:
                break
            document_ids = [doc.id for doc in documents]
            sheet_names_by_document_id: dict[UUID, list[str]] = {}
            active_sheet_only_by_document_id: dict[UUID, bool] = {}
            for document in documents:
                run_options = self._documents_service.read_upload_run_options(document.attributes)
                if run_options and run_options.input_sheet_names is not None:
                    sheet_names_by_document_id[document.id] = list(run_options.input_sheet_names)
                if run_options and run_options.active_sheet_only:
                    active_sheet_only_by_document_id[document.id] = True
            try:
                runs = await self.prepare_runs_batch(
                    configuration_id=configuration.id,
                    document_ids=document_ids,
                    options=RunBatchCreateOptions(),
                    input_sheet_names_by_document_id=sheet_names_by_document_id or None,
                    active_sheet_only_by_document_id=active_sheet_only_by_document_id or None,
                )
            except RunQueueFullError:
                logger.warning(
                    "run.pending.enqueue.queue_full",
                    extra=log_context(
                        workspace_id=configuration.workspace_id,
                        configuration_id=configuration.id,
                    ),
                )
                break
            total += len(runs)
            if len(document_ids) < limit:
                break

        if total:
            logger.info(
                "run.pending.enqueue.completed",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    count=total,
                ),
            )
        return total

    async def is_processing_paused(self, *, workspace_id: UUID) -> bool:
        return await self._processing_paused(workspace_id)

    async def _maybe_enqueue_pending_runs(self, *, workspace_id: UUID) -> None:
        try:
            configuration = await self._configs.get_active(workspace_id)
        except Exception:  # pragma: no cover - defensive guard
            logger.exception(
                "run.pending.enqueue.auto.failed",
                extra=log_context(workspace_id=workspace_id),
            )
            return
        if configuration is None:
            return
        try:
            await self.enqueue_pending_runs_for_configuration(configuration_id=configuration.id)
        except Exception:  # pragma: no cover - defensive guard
            logger.exception(
                "run.pending.enqueue.auto.failed",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration.id,
                ),
            )

    async def expire_stuck_runs(self) -> int:
        horizon = utc_now()
        stmt = (
            select(Run)
            .where(
                Run.status == RunStatus.RUNNING,
                Run.claim_expires_at.is_not(None),
                Run.claim_expires_at < horizon,
            )
            .order_by(Run.claim_expires_at.asc())
        )
        result = await self._session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0

        message = "Run lease expired"
        for run in runs:
            if run.attempt_count >= run.max_attempts:
                run_dir = self._run_dir_for_run(
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                )
                paths_snapshot = self._finalize_paths(
                    run_dir=run_dir,
                    default_paths=RunPathsSnapshot(),
                )
                completion = await self._complete_run(
                    run,
                    status=RunStatus.FAILED,
                    exit_code=1,
                    error_message=message,
                )
                await self._emit_api_event(
                    run=completion,
                    type_="run.complete",
                    payload=self._run_completed_payload(
                        run=completion,
                        paths=paths_snapshot,
                        failure_stage="run",
                        failure_code="lease_expired",
                        failure_message=message,
                    ),
                )
                continue

            delay_seconds = self._retry_delay_seconds(run.attempt_count)
            run.status = RunStatus.QUEUED
            run.started_at = None
            run.completed_at = None
            run.cancelled_at = None
            run.exit_code = None
            run.available_at = utc_now() + timedelta(seconds=delay_seconds)
            run.error_message = message
            run.claimed_by = None
            run.claim_expires_at = None
            await self._session.commit()

            document = await self._touch_document_status(
                run=run,
                status=DocumentStatus.UPLOADED,
            )
            if document is not None:
                await self._session.commit()
                await self._emit_document_upsert(document)

        logger.warning(
            "run.stuck.expired",
            extra=log_context(count=len(runs)),
        )
        return len(runs)

    async def expire_stuck_builds(self) -> int:
        return await self._builds_service.expire_stuck_builds()

    async def _remaining_queue_capacity(self) -> int | None:
        limit = self._settings.queue_size
        if not limit:
            return None
        queued = await self._runs.count_queued()
        return max(limit - queued, 0)

    async def _pending_documents(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        limit: int,
    ) -> list[Document]:
        if limit <= 0:
            return []
        pending_run_exists = (
            select(Run.id)
            .where(
                Run.input_document_id == Document.id,
                Run.configuration_id == configuration_id,
            )
            .limit(1)
            .exists()
        )
        stmt = (
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                Document.status == DocumentStatus.UPLOADED,
                Document.deleted_at.is_(None),
                ~pending_run_exists,
            )
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _require_active_run(
        self,
        *,
        configuration_id: UUID,
        document_id: UUID,
    ) -> Run:
        runs = await self._runs.list_active_for_documents(
            configuration_id=configuration_id,
            document_ids=[document_id],
        )
        if not runs:
            raise RuntimeError(f"No active run found for document {document_id}")
        return runs[0]

    async def _insert_runs_for_documents(
        self,
        *,
        configuration: Configuration,
        document_ids: Sequence[UUID],
        input_sheet_names_by_document_id: dict[UUID, list[str] | None] | None,
        run_options_by_document_id: dict[UUID, dict[str, Any] | None] | None,
        document_status: DocumentStatus | None,
        existing_statuses: Sequence[RunStatus] | None,
    ) -> None:
        if not document_ids:
            return

        base_stmt = select(Document.id).where(
            Document.workspace_id == configuration.workspace_id,
            Document.deleted_at.is_(None),
            Document.id.in_(document_ids),
        )
        if document_status is not None:
            base_stmt = base_stmt.where(Document.status == document_status)
        result = await self._session.execute(base_stmt)
        eligible_ids = [doc_id for (doc_id,) in result.all()]
        if not eligible_ids:
            return

        if existing_statuses:
            existing_stmt = select(Run.input_document_id).where(
                Run.configuration_id == configuration.id,
                Run.input_document_id.in_(eligible_ids),
                Run.status.in_(list(existing_statuses)),
            )
            existing_result = await self._session.execute(existing_stmt)
            existing_ids = {doc_id for (doc_id,) in existing_result.all()}
            eligible_ids = [doc_id for doc_id in eligible_ids if doc_id not in existing_ids]
            if not eligible_ids:
                return

        def build_rows(ids: Sequence[UUID]) -> list[dict[str, Any]]:
            now = utc_now()
            return [
                {
                    "configuration_id": configuration.id,
                    "workspace_id": configuration.workspace_id,
                    "input_document_id": doc_id,
                    "input_sheet_names": (
                        input_sheet_names_by_document_id.get(doc_id)
                        if input_sheet_names_by_document_id
                        else None
                    ),
                    "run_options": (
                        run_options_by_document_id.get(doc_id)
                        if run_options_by_document_id
                        else None
                    ),
                    "status": RunStatus.QUEUED,
                    "available_at": now,
                    "attempt_count": 0,
                    "max_attempts": self._run_max_attempts,
                }
                for doc_id in ids
            ]

        rows = build_rows(eligible_ids)
        for attempt in range(2):
            try:
                await self._session.execute(insert(Run), rows)
                await self._session.commit()
                return
            except IntegrityError:
                await self._session.rollback()
                if attempt:
                    raise
                if existing_statuses:
                    existing_stmt = select(Run.input_document_id).where(
                        Run.configuration_id == configuration.id,
                        Run.input_document_id.in_(eligible_ids),
                        Run.status.in_(list(existing_statuses)),
                    )
                    existing_result = await self._session.execute(existing_stmt)
                    existing_ids = {doc_id for (doc_id,) in existing_result.all()}
                    remaining = [doc_id for doc_id in eligible_ids if doc_id not in existing_ids]
                    if not remaining:
                        return
                    rows = build_rows(remaining)

    def _retry_delay_seconds(self, attempt_count: int) -> int:
        base = DEFAULT_BACKOFF_BASE_SECONDS
        exponent = max(attempt_count - 1, 0)
        delay = base * (2**exponent)
        return min(DEFAULT_BACKOFF_MAX_SECONDS, delay)

    async def _requeue_run(
        self,
        *,
        run: Run,
        reason: str,
        worker_id: str,
        delay_seconds: int,
        attempt_delta: int = 0,
        error_message: str | None = None,
    ) -> Run | None:
        now = utc_now()
        available_at = now + timedelta(seconds=delay_seconds)
        values: dict[str, Any] = {
            "status": RunStatus.QUEUED,
            "started_at": None,
            "completed_at": None,
            "cancelled_at": None,
            "exit_code": None,
            "available_at": available_at,
            "claimed_by": None,
            "claim_expires_at": None,
        }
        if attempt_delta:
            values["attempt_count"] = max(run.attempt_count + attempt_delta, 0)
        values["error_message"] = error_message

        # CAS completion: only the current lease holder may finalize the run.
        stmt = (
            update(Run)
            .where(
                Run.id == run.id,
                Run.status == RunStatus.RUNNING,
                Run.claimed_by == worker_id,
            )
            .values(**values)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        if not result.rowcount:
            logger.warning(
                "run.requeue.claim_lost",
                extra=log_context(run_id=run.id, reason=reason),
            )
            return None

        document = await self._touch_document_status(
            run=run,
            status=DocumentStatus.UPLOADED,
        )
        if document is not None:
            await self._session.commit()
            await self._emit_document_upsert(document)

        await self._session.refresh(run)
        logger.info(
            "run.requeued",
            extra=log_context(run_id=run.id, reason=reason),
        )
        return run

    async def _maybe_retry_run(
        self,
        *,
        run: Run,
        worker_id: str,
        error_message: str | None,
    ) -> bool:
        if run.attempt_count >= run.max_attempts:
            return False
        delay_seconds = self._retry_delay_seconds(run.attempt_count)
        requeued = await self._requeue_run(
            run=run,
            reason="run_failed",
            worker_id=worker_id,
            delay_seconds=delay_seconds,
            error_message=error_message,
        )
        return requeued is not None

    async def _ensure_run_build(
        self,
        *,
        run: Run,
        options: RunCreateOptions,
    ) -> Build:
        if run.build_id is not None:
            return await self._builds_service.get_build_or_raise(
                run.build_id,
                workspace_id=run.workspace_id,
            )

        build, _ = await self._builds_service.ensure_build_for_run(
            workspace_id=run.workspace_id,
            configuration_id=run.configuration_id,
            force_rebuild=options.force_rebuild,
            run_id=run.id,
            reason="run_claimed",
        )
        run.build_id = build.id
        await self._session.commit()
        await self._session.refresh(run)
        return build

    async def _mark_run_started(self, *, run: Run) -> None:
        document = await self._touch_document_status(
            run=run,
            status=DocumentStatus.PROCESSING,
        )
        if document is None:
            return
        await self._session.commit()
        await self._emit_document_upsert(document)

    async def _enforce_queue_capacity(self, *, requested: int = 1) -> None:
        limit = self._settings.queue_size
        if not limit or requested <= 0:
            return
        queued = await self._runs.count_queued()
        if queued + requested > limit:
            raise RunQueueFullError(f"Run queue is full (limit {limit})")

    async def _fail_run_due_to_build(
        self,
        *,
        run: Run,
        build: Build,
        worker_id: str,
    ) -> AsyncIterator[EventRecord]:
        failure_code = "build_failed" if build.status is BuildStatus.FAILED else "build_cancelled"
        error_message = build.error_message or (
            f"Configuration {build.configuration_id} build {build.status.value}"
        )
        yield await self._emit_api_event(
            run=run,
            type_="console.line",
            payload={
                "scope": "run",
                "stream": "stderr",
                "level": "error",
                "message": error_message,
            },
        )
        run_dir = self._run_dir_for_run(
            workspace_id=run.workspace_id,
            run_id=run.id,
        )
        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )
        completion = await self._complete_run_if_owned(
            run=run,
            status=RunStatus.FAILED,
            exit_code=1,
            error_message=error_message,
            worker_id=worker_id,
        )
        if completion is None:
            return
        yield await self._emit_api_event(
            run=completion,
            type_="run.complete",
            payload=self._run_completed_payload(
                run=completion,
                paths=paths_snapshot,
                failure_stage="build",
                failure_code=failure_code,
                failure_message=error_message,
            ),
        )

    async def _execution_context_for_run(self, run_id: UUID) -> RunExecutionContext:
        run = await self._require_run(run_id)
        if run.build_id is None:
            raise RuntimeError(f"Run {run_id} is missing build metadata")
        return RunExecutionContext(
            run_id=run.id,
            configuration_id=run.configuration_id,
            workspace_id=run.workspace_id,
            build_id=run.build_id,
        )

    async def run_to_completion(
        self,
        *,
        run_id: UUID,
        options: RunCreateOptions | None = None,
        worker_id: str,
    ) -> None:
        """Execute the run, exhausting the event stream."""

        if options is None:
            run = await self._require_run(run_id)
            options = await self.load_run_options(run)

        if not worker_id:
            raise ValueError("worker_id is required to execute runs")

        logger.info(
            "run.execute.start",
            extra=log_context(
                run_id=run_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )
        async for _ in self.stream_run(
            run_id=run_id,
            options=options,
            worker_id=worker_id,
        ):
            pass
        logger.info(
            "run.execute.completed",
            extra=log_context(
                run_id=run_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )

    async def stream_run(
        self,
        *,
        run_id: UUID,
        options: RunCreateOptions,
        worker_id: str,
    ) -> AsyncIterator[RunStreamFrame]:
        """Iterate through run events while executing the engine."""

        run = await self._require_run(run_id)
        if run.status is not RunStatus.RUNNING or run.claimed_by != worker_id:
            logger.warning(
                "run.stream.claim.mismatch",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    status=run.status.value,
                    claimed_by=run.claimed_by,
                ),
            )
            return
        logger.debug(
            "run.stream.start",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )

        try:
            async for event in self._stream_run_steps(
                run=run,
                options=options,
                worker_id=worker_id,
            ):
                yield event
        except Exception as exc:  # pragma: no cover - defensive orchestration guard
            async for event in self._handle_stream_failure(
                run=run,
                options=options,
                error=exc,
                worker_id=worker_id,
            ):
                yield event

    async def _stream_run_steps(
        self,
        *,
        run: Run,
        options: RunCreateOptions,
        worker_id: str,
    ) -> AsyncIterator[RunStreamFrame]:
        """Orchestrate run execution and yield events; raised exceptions are handled upstream."""

        if run.status is not RunStatus.RUNNING or run.claimed_by != worker_id:
            logger.warning(
                "run.stream.claim.lost",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    status=run.status.value,
                    claimed_by=run.claimed_by,
                ),
            )
            return

        mode_literal = "validate" if options.validate_only else "execute"

        queued_event = await self._ensure_run_queued_event(
            run=run,
            mode_literal=mode_literal,
            options=options,
        )
        if queued_event:
            yield queued_event

        build = await self._ensure_run_build(run=run, options=options)
        if build.status in (BuildStatus.FAILED, BuildStatus.CANCELLED):
            async for event in self._fail_run_due_to_build(
                run=run,
                build=build,
                worker_id=worker_id,
            ):
                yield event
            return
        if build.status is not BuildStatus.READY:
            await self._builds_service.launch_build_if_needed(
                build=build,
                reason="run_requested",
                run_id=run.id,
            )
            await self._requeue_run(
                run=run,
                reason="build_not_ready",
                worker_id=worker_id,
                delay_seconds=DEFAULT_REQUEUE_DELAY_SECONDS,
                attempt_delta=-1,
            )
            return

        await self._mark_run_started(run=run)
        yield await self._emit_api_event(
            run=run,
            type_="run.start",
            payload={
                "status": "in_progress",
                "mode": mode_literal,
            },
        )
        safe_mode = await self._safe_mode_status()

        # Emit a one-time console banner describing the mode, if applicable.
        mode_message = self._format_mode_message(options)
        if mode_message:
            yield await self._emit_api_event(
                run=run,
                type_="console.line",
                payload={
                    "scope": "run",
                    "stream": "stdout",
                    "level": "info",
                    "message": mode_message,
                },
            )

        # Validation-only short circuit: we never touch the engine.
        if options.validate_only:
            async for event in self._stream_validate_only_run(
                run=run,
                mode_literal=mode_literal,
                worker_id=worker_id,
            ):
                yield event
            return

        # Safe mode short circuit: log the skip and exit.
        if safe_mode.enabled:
            async for event in self._stream_safe_mode_skip(
                run=run,
                mode_literal=mode_literal,
                safe_mode=safe_mode,
                worker_id=worker_id,
            ):
                yield event
            return

        # Full engine execution: delegate to the process runner + supervisor.
        context = RunExecutionContext(
            run_id=run.id,
            configuration_id=run.configuration_id,
            workspace_id=run.workspace_id,
            build_id=build.id,
        )
        async for event in self._stream_engine_run(
            run=run,
            context=context,
            options=options,
            mode_literal=mode_literal,
            safe_mode_enabled=safe_mode.enabled,
            worker_id=worker_id,
        ):
            yield event

    async def _handle_stream_failure(
        self,
        *,
        run: Run,
        options: RunCreateOptions,
        error: Exception,
        worker_id: str,
    ) -> AsyncIterator[RunStreamFrame]:
        """Emit console + completion events when unexpected orchestration errors occur."""

        logger.exception(
            "run.stream.unhandled_error",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
            exc_info=error,
        )

        refreshed = await self._runs.get(run.id)
        if refreshed is None:
            return
        if refreshed.status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED):
            return

        message = f"ADE run orchestration failed: {error}"
        yield await self._emit_api_event(
            run=refreshed,
            type_="console.line",
            payload={
                "scope": "run",
                "stream": "stderr",
                "level": "error",
                "message": message,
            },
        )

        run_dir = self._run_dir_for_run(
            workspace_id=refreshed.workspace_id,
            run_id=refreshed.id,
        )
        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )
        completion = await self._complete_run_if_owned(
            run=refreshed,
            status=RunStatus.FAILED,
            exit_code=None,
            error_message=str(error),
            worker_id=worker_id,
        )
        if completion is None:
            return
        yield await self._emit_api_event(
            run=completion,
            type_="run.complete",
            payload=self._run_completed_payload(
                run=completion,
                paths=paths_snapshot,
                failure_stage="run",
                failure_code="orchestration_error",
                failure_message=str(error),
            ),
        )

    async def handle_background_failure(
        self,
        *,
        run_id: UUID,
        options: RunCreateOptions,
        error: Exception,
    ) -> AsyncIterator[EventRecord]:
        """Surface background task failures via console + completion events."""

        run = await self._runs.get(run_id)
        if run is None or run.claimed_by is None:
            return

        async for event in self._handle_stream_failure(
            run=run,
            options=options,
            error=error,
            worker_id=run.claimed_by,
        ):
            if isinstance(event, dict):
                yield event

    # --------------------------------------------------------------------- #
    # Public read APIs (runs, summaries, events, outputs)
    # --------------------------------------------------------------------- #

    async def get_run(self, run_id: UUID) -> Run | None:
        """Return the run instance for ``run_id`` if it exists."""

        logger.debug(
            "run.get.start",
            extra=log_context(run_id=run_id),
        )
        run = await self._runs.get(run_id)
        if run is None:
            logger.debug(
                "run.get.miss",
                extra=log_context(run_id=run_id),
            )
        else:
            logger.debug(
                "run.get.hit",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    status=run.status.value,
                ),
            )
        return run

    async def get_run_metrics(self, *, run_id: UUID) -> RunMetrics | None:
        """Return persisted run metrics for ``run_id`` when available."""

        run = await self._require_run(run_id)
        return await self._runs.get_metrics(run.id)

    async def list_run_fields(self, *, run_id: UUID) -> list[RunField]:
        """Return field summaries for ``run_id``."""

        run = await self._require_run(run_id)
        return await self._runs.list_fields(run.id)

    async def list_run_columns(
        self,
        *,
        run_id: UUID,
        filters: RunColumnFilters,
    ) -> list[RunTableColumn]:
        """Return detected columns for ``run_id`` with optional filters."""

        run = await self._require_run(run_id)
        return await self._runs.list_columns(run_id=run.id, filters=filters)

    async def get_run_events(
        self,
        *,
        run_id: UUID,
        after_sequence: int | None = None,
        limit: int = DEFAULT_EVENTS_PAGE_LIMIT,
    ) -> tuple[list[EventRecord], int | None]:
        """Return telemetry events for ``run_id`` with optional paging."""

        logger.debug(
            "run.events.get.start",
            extra=log_context(run_id=run_id, after_sequence=after_sequence, limit=limit),
        )
        run = await self._require_run(run_id)
        events: list[EventRecord] = []
        next_after: int | None = None
        stream = self._event_stream_for_run(run)
        cursor = after_sequence or 0
        for event in stream.iter_persisted(after_sequence=after_sequence):
            cursor += 1
            events.append(event)
            if len(events) >= limit:
                next_after = cursor
                break

        logger.info(
            "run.events.get.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                count=len(events),
                next_after_sequence=next_after,
            ),
        )
        return events, next_after

    async def list_runs(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID | None = None,
        filters: RunFilters,
        order_by: OrderBy,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[RunResource]:
        """Return paginated runs for ``workspace_id`` with optional filters."""

        logger.debug(
            "run.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                filters=filters.model_dump(exclude_none=True),
                order_by=str(order_by),
                page=page,
                page_size=page_size,
                include_total=include_total,
            ),
        )

        page_result = await self._runs.list_by_workspace(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            filters=filters,
            order_by=order_by,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )
        resources = [await self.to_resource(run) for run in page_result.items]
        response = Page(
            items=resources,
            page=page_result.page,
            page_size=page_result.page_size,
            has_next=page_result.has_next,
            has_previous=page_result.has_previous,
            total=page_result.total,
        )

        logger.info(
            "run.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                page=response.page,
                page_size=response.page_size,
                count=len(response.items),
                total=response.total,
            ),
        )
        return response

    async def list_runs_for_configuration(
        self,
        *,
        configuration_id: UUID,
        filters: RunFilters,
        order_by: OrderBy,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[RunResource]:
        """Return paginated runs for ``configuration_id`` scoped to its workspace."""

        configuration = await self._resolve_configuration(configuration_id)
        return await self.list_runs(
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            filters=filters,
            order_by=order_by,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )

    async def to_resource(self, run: Run) -> RunResource:
        """Convert ``run`` into its API representation."""

        run_dir = self._run_dir_for_run(
            workspace_id=run.workspace_id,
            run_id=run.id,
        )
        paths = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )

        processed_file = self._resolve_processed_file(
            paths=paths,
        )

        # Timing and failure info
        started_at = self._ensure_utc(run.started_at)
        completed_at = self._ensure_utc(run.completed_at)
        duration_seconds = (
            (completed_at - started_at).total_seconds() if started_at and completed_at else None
        )

        failure_code = None
        failure_stage = None
        failure_message = run.error_message

        input_meta = await self._build_input_metadata(
            run=run,
            files_counts={},
            sheets_counts={},
        )
        output_meta = await self._build_output_metadata(
            run=run,
            run_dir=run_dir,
            paths=paths,
            processed_file=processed_file,
        )
        links = self._links(run.id)

        return RunResource(
            id=run.id,
            workspace_id=run.workspace_id,
            configuration_id=run.configuration_id,
            build_id=run.build_id,
            status=run.status,
            failure_code=failure_code,
            failure_stage=failure_stage,
            failure_message=failure_message,
            engine_version=None,
            config_version=None,
            env_reason=None,
            env_reused=None,
            created_at=self._ensure_utc(run.created_at) or utc_now(),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            exit_code=run.exit_code,
            input=input_meta,
            output=output_meta,
            links=links,
            events_url=links.events,
            events_stream_url=links.events_stream,
            events_download_url=links.events_download,
        )

    def _resolve_processed_file(
        self,
        *,
        paths: RunPathsSnapshot,
    ) -> str | None:
        processed_file = paths.processed_file
        return processed_file

    async def _build_input_metadata(
        self,
        *,
        run: Run,
        files_counts: dict[str, Any],
        sheets_counts: dict[str, Any],
    ) -> RunInput:
        document_id = str(run.input_document_id) if run.input_document_id else None
        filename: str | None = None
        content_type: str | None = None
        size_bytes: int | None = None
        download_url: str | None = None

        if document_id:
            download_url = f"/api/v1/runs/{run.id}/input/download"
            try:
                document = await self._require_document(
                    workspace_id=run.workspace_id,
                    document_id=run.input_document_id,  # type: ignore[arg-type]
                )
                filename = document.original_filename
                content_type = document.content_type
                size_bytes = document.byte_size
            except RunDocumentMissingError:
                logger.warning(
                    "run.input.metadata.missing_document",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                        document_id=document_id,
                    ),
                )

        return RunInput(
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            download_url=download_url,
            input_sheet_names=run.input_sheet_names,
            input_file_count=files_counts.get("total"),
            input_sheet_count=sheets_counts.get("total"),
        )

    async def _build_output_metadata(
        self,
        *,
        run: Run,
        run_dir: Path,
        paths: RunPathsSnapshot,
        processed_file: str | None,
    ) -> RunOutput:
        output_path = paths.output_path or self._relative_output_path(run_dir / "output", run_dir)
        output_file: Path | None = None
        if output_path:
            candidate = (run_dir / output_path).resolve()
            try:
                candidate.relative_to(run_dir)
            except ValueError:
                candidate = None
            if candidate and candidate.is_file():
                output_file = candidate

        ready = bool(output_file) and run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }

        filename: str | None = None
        size_bytes: int | None = None
        content_type: str | None = None

        if output_file:
            filename = output_file.name
            try:
                size_bytes = output_file.stat().st_size
            except OSError:
                size_bytes = None
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        return RunOutput(
            ready=ready,
            download_url=f"/api/v1/runs/{run.id}/output/download",
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            has_output=bool(output_path),
            output_path=output_path,
            processed_file=str(processed_file) if processed_file else None,
        )

    @staticmethod
    def _links(run_id: UUID) -> RunLinks:
        base = f"/api/v1/runs/{run_id}"
        events = f"{base}/events"
        events_stream = f"{events}/stream"
        events_download = f"{events}/download"
        output_metadata = f"{base}/output"
        output_download = f"{output_metadata}/download"
        input_metadata = f"{base}/input"
        input_download = f"{input_metadata}/download"

        return RunLinks(
            self=base,
            events=events,
            events_stream=events_stream,
            events_download=events_download,
            logs=events_download,
            input=input_metadata,
            input_download=input_download,
            output=output_download,
            output_download=output_download,
            output_metadata=output_metadata,
        )

    async def get_run_input_metadata(
        self,
        *,
        run_id: UUID,
    ) -> RunInput:
        run = await self._require_run(run_id)
        resource = await self.to_resource(run)
        if resource.input.document_id is None:
            raise RunInputMissingError("Run input is unavailable")
        if resource.input.filename is None:
            raise RunDocumentMissingError("Run input file is unavailable")
        return resource.input

    async def stream_run_input(
        self,
        *,
        run_id: UUID,
    ) -> tuple[Run, Document, AsyncIterator[bytes]]:
        run = await self._require_run(run_id)
        if not run.input_document_id:
            raise RunInputMissingError("Run input is unavailable")
        document = await self._require_document(
            workspace_id=run.workspace_id,
            document_id=run.input_document_id,
        )
        storage = self._storage_for(run.workspace_id)
        path = storage.path_for(document.stored_uri)
        exists = await asyncio.to_thread(path.exists)
        if not exists:
            logger.warning(
                "run.input.stream.missing_file",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    document_id=document.id,
                    stored_uri=document.stored_uri,
                ),
            )
            raise RunDocumentMissingError("Run input file is unavailable")

        stream = storage.stream(document.stored_uri)

        async def _guarded() -> AsyncIterator[bytes]:
            try:
                async for chunk in stream:
                    yield chunk
            except FileNotFoundError as exc:
                logger.warning(
                    "run.input.stream.file_lost",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                        document_id=document.id,
                        stored_uri=document.stored_uri,
                    ),
                )
                raise RunDocumentMissingError("Run input file is unavailable") from exc

        return run, document, _guarded()

    async def get_run_output_metadata(
        self,
        *,
        run_id: UUID,
    ) -> RunOutput:
        run = await self._require_run(run_id)
        resource = await self.to_resource(run)
        return resource.output

    async def resolve_output_for_download(
        self,
        *,
        run_id: UUID,
    ) -> tuple[Run, Path]:
        run = await self._require_run(run_id)
        if run.status in {
            RunStatus.QUEUED,
            RunStatus.RUNNING,
        }:
            raise RunOutputNotReadyError("Run output is not available until the run completes.")
        try:
            path = await self.resolve_output_file(run_id=run_id)
        except RunOutputMissingError as err:
            if run.status is RunStatus.FAILED:
                raise RunOutputMissingError(
                    "Run failed and no output is available",
                ) from err
            raise
        return run, path

    async def get_logs_file_path(self, *, run_id: UUID) -> Path:
        """Return the raw log stream path for ``run_id`` when available."""

        logger.debug(
            "run.logs.file_path.start",
            extra=log_context(run_id=run_id),
        )
        run = await self._require_run(run_id)
        logs_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id) / "logs"
        logs_path = logs_dir / "events.ndjson"
        if not logs_path.is_file():
            logger.warning(
                "run.logs.file_path.missing",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(logs_path),
                ),
            )
            raise RunLogsFileMissingError("Run log stream is unavailable")
        logger.info(
            "run.logs.file_path.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                path=str(logs_path),
            ),
        )
        return logs_path

    async def resolve_output_file(
        self,
        *,
        run_id: UUID,
    ) -> Path:
        """Return the absolute path for ``relative_path`` in ``run_id`` outputs."""

        logger.debug(
            "run.outputs.resolve.start",
            extra=log_context(run_id=run_id),
        )
        run = await self._require_run(run_id)
        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)

        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )
        output_relative = paths_snapshot.output_path or self._relative_output_path(
            run_dir / "output", run_dir
        )
        if not output_relative:
            logger.warning(
                "run.outputs.resolve.missing_root",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(run_dir / "output"),
                ),
            )
            raise RunOutputMissingError("Run output is unavailable")

        candidate = (run_dir / output_relative).resolve()
        try:
            candidate.relative_to(run_dir)
        except ValueError:
            logger.warning(
                "run.outputs.resolve.outside_directory",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(candidate),
                ),
            )
            raise RunOutputMissingError("Requested output is outside the run directory") from None

        if not candidate.is_file():
            logger.warning(
                "run.outputs.resolve.not_found",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(candidate),
                ),
            )
            raise RunOutputMissingError("Requested output file not found")

        logger.info(
            "run.outputs.resolve.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                path=str(candidate),
            ),
        )
        return candidate

    def run_directory(self, *, workspace_id: UUID, run_id: UUID) -> Path:
        """Return the canonical run directory for a given ``run_id``."""

        path = self._run_dir_for_run(workspace_id=workspace_id, run_id=run_id)
        logger.debug(
            "run.directory.resolve",
            extra=log_context(workspace_id=workspace_id, run_id=run_id, path=str(path)),
        )
        return path

    def run_relative_path(self, path: Path, *, base_dir: Path | None = None) -> str:
        """Return ``path`` relative to ``base_dir`` (or runs root), validating traversal."""

        root = (base_dir or self._runs_dir).resolve()
        candidate = path.resolve()
        try:
            value = str(candidate.relative_to(root))
        except ValueError:  # pragma: no cover - defensive guard
            logger.warning(
                "run.path.escape_detected",
                extra=log_context(path=str(candidate)),
            )
            raise RunOutputMissingError("Requested path escapes runs directory") from None
        return value

    # --------------------------------------------------------------------- #
    # Internal helpers: paths, summaries, manifests
    # --------------------------------------------------------------------- #

    def _relative_if_exists(
        self,
        path: str | Path | None,
        *,
        run_dir: Path | None = None,
    ) -> str | None:
        if path is None:
            return None

        candidates: list[Path] = []
        candidate = Path(path)
        candidates.append(candidate)
        if run_dir is not None and not candidate.is_absolute():
            candidates.append(run_dir / candidate)

        for option in candidates:
            if not option.exists():
                continue
            try:
                return self.run_relative_path(option, base_dir=run_dir)
            except RunOutputMissingError:
                continue
        return None

    def _relative_output_path(self, output_dir: Path, run_dir: Path) -> str | None:
        if not output_dir.exists() or not output_dir.is_dir():
            return None
        normalized = output_dir / "normalized.xlsx"
        relative = self._relative_if_exists(normalized, run_dir=run_dir)
        if relative:
            return relative
        for path in sorted(p for p in output_dir.rglob("*") if p.is_file()):
            relative = self._relative_if_exists(path, run_dir=run_dir)
        if relative is not None:
            return relative
        return None

    def _run_relative_hint(self, path: str | Path | None, *, run_dir: Path | None) -> str | None:
        """Return ``path`` relative to the run directory without hitting the filesystem."""

        if path is None or run_dir is None:
            return None

        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (run_dir / candidate).resolve()
        try:
            return self.run_relative_path(candidate, base_dir=run_dir)
        except RunOutputMissingError:
            return None

    @staticmethod
    def _document_descriptor(document: Document) -> dict[str, Any]:
        return {
            "document_id": str(document.id),
            "display_name": document.original_filename,
            "name": document.original_filename,
            "original_filename": document.original_filename,
            "content_type": document.content_type,
            "byte_size": document.byte_size,
        }

    def _finalize_paths(
        self,
        *,
        run_dir: Path,
        default_paths: RunPathsSnapshot,
    ) -> RunPathsSnapshot:
        """Merge inferred filesystem paths for events and outputs."""

        snapshot = RunPathsSnapshot(
            events_path=default_paths.events_path,
            output_path=default_paths.output_path,
            processed_file=default_paths.processed_file,
        )

        # Events path: default to <run_dir>/logs/events.ndjson, if it exists.
        if not snapshot.events_path:
            candidate = run_dir / "logs" / "events.ndjson"
            snapshot.events_path = self._run_relative_hint(candidate, run_dir=run_dir)
        if not snapshot.events_path:
            logs_dir = run_dir / "logs"
            if logs_dir.exists():
                for path in sorted(logs_dir.glob("*_engine_events.ndjson")):
                    snapshot.events_path = self._run_relative_hint(path, run_dir=run_dir)
                    if snapshot.events_path:
                        break

        # Output path: if not provided, infer from <run_dir>/output.
        if not snapshot.output_path:
            snapshot.output_path = self._relative_output_path(run_dir / "output", run_dir)

        return snapshot

    def _run_completed_payload(
        self,
        *,
        run: Run,
        paths: RunPathsSnapshot,
        failure_stage: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> dict[str, Any]:
        failure: dict[str, Any] | None = None
        if any([failure_stage, failure_code, failure_message]):
            failure = {
                "stage": failure_stage,
                "code": failure_code,
                "message": failure_message,
            }

        def _dt_iso(dt: datetime | None) -> str | None:
            normalized = self._ensure_utc(dt)
            return normalized.isoformat() if normalized else None

        return {
            "status": getattr(run.status, "value", run.status),
            "failure": failure,
            "execution": {
                "exit_code": run.exit_code,
                "started_at": _dt_iso(run.started_at),
                "completed_at": _dt_iso(run.completed_at),
                "duration_ms": self._duration_ms(run),
            },
            "artifacts": {
                "output_path": paths.output_path,
                "processed_file": paths.processed_file,
                "events_path": paths.events_path,
            },
        }

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return None

    @staticmethod
    def _resolve_completion(
        return_code: int,
    ) -> tuple[RunStatus, str | None]:
        """Resolve final RunStatus and error message from exit code."""

        status = RunStatus.SUCCEEDED if return_code == 0 else RunStatus.FAILED
        error_message: str | None = (
            None if status is RunStatus.SUCCEEDED else f"Process exited with {return_code}"
        )

        return status, error_message

    # --------------------------------------------------------------------- #
    # Engine execution helpers
    # --------------------------------------------------------------------- #

    async def _execute_engine(
        self,
        *,
        run: Run,
        context: RunExecutionContext,
        options: RunCreateOptions,
        safe_mode_enabled: bool = False,
    ) -> AsyncIterator[RunStreamFrame]:
        """Invoke the engine process and stream its output lines."""

        logger.info(
            "run.engine.execute.start",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
                safe_mode_enabled=safe_mode_enabled,
            ),
        )

        build = await self._builds_service.get_build_or_raise(
            context.build_id,
            workspace_id=context.workspace_id,
        )
        venv_path = await self._builds_service.ensure_local_env(build=build)
        python = venv_python_path(venv_path)
        active_sheet_only = bool(getattr(options, "active_sheet_only", False))
        selected_sheet_names = self._select_input_sheet_names(options)
        if not active_sheet_only and not selected_sheet_names and run.input_sheet_names:
            selected_sheet_names = list(run.input_sheet_names)

        env = self._build_env(
            venv_path,
            options,
            context,
            input_sheet_name=selected_sheet_names[0] if selected_sheet_names else None,
        )

        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
        run_dir.mkdir(parents=True, exist_ok=True)

        input_document_id = options.input_document_id or run.input_document_id
        if not input_document_id:
            logger.warning(
                "run.engine.execute.input_missing",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                ),
            )
            raise RunInputMissingError("Input document is required for run execution")

        staged_input = await self._stage_input_document(
            workspace_id=context.workspace_id,
            document_id=UUID(str(input_document_id)),
            run_dir=run_dir,
        )

        # Canonical paths we expect after execution
        output_dir = run_dir / "output"
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        config_path = await self._storage.ensure_config_path(
            workspace_id=context.workspace_id,
            configuration_id=context.configuration_id,
        )

        command = [str(python), "-m", "ade_engine", "process", "file"]
        command.extend(["--input", str(staged_input)])
        command.extend(["--output-dir", str(output_dir)])
        command.extend(["--logs-dir", str(logs_dir)])
        command.extend(["--config-package", str(config_path)])
        command.extend(["--log-format", "ndjson"])
        log_level = getattr(options, "log_level", None) or "INFO"
        command.extend(["--log-level", str(log_level)])
        if active_sheet_only:
            command.append("--active-sheet-only")
        else:
            for sheet_name in selected_sheet_names:
                command.extend(["--input-sheet", sheet_name])

        runner = EngineSubprocessRunner(
            command=command,
            env=env,
        )

        # We expect API-level events to be written under <run>/logs/events.ndjson
        log_suffix = "engine_events.ndjson"
        output_filename = f"{staged_input.stem}_normalized.xlsx"
        paths_snapshot = RunPathsSnapshot(
            events_path=str(logs_dir / f"{staged_input.stem}_{log_suffix}"),
            output_path=str(output_dir / output_filename),
            processed_file=staged_input.name,
        )

        timeout_seconds = self._settings.run_timeout_seconds
        try:
            if timeout_seconds:
                async with asyncio.timeout(timeout_seconds):
                    async for frame in runner.stream():
                        yield frame
            else:
                async for frame in runner.stream():
                    yield frame
        except TimeoutError:
            await runner.terminate()
            timeout_message = f"Run timed out after {timeout_seconds}s"
            paths_snapshot = self._finalize_paths(
                run_dir=run_dir,
                default_paths=paths_snapshot,
            )
            yield RunExecutionResult(
                status=RunStatus.FAILED,
                return_code=None,
                paths_snapshot=paths_snapshot,
                error_message=timeout_message,
            )
            return

        # Process completion and summarize.
        return_code = runner.returncode if runner.returncode is not None else 1
        status, error_message = self._resolve_completion(return_code)

        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=paths_snapshot,
        )

        logger.info(
            "run.engine.execute.completed",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                status=status.value,
                exit_code=return_code,
            ),
        )

        yield RunExecutionResult(
            status=status,
            return_code=return_code,
            paths_snapshot=paths_snapshot,
            error_message=error_message,
        )

    async def _stream_validate_only_run(
        self,
        *,
        run: Run,
        mode_literal: str,
        worker_id: str,
    ) -> AsyncIterator[RunStreamFrame]:
        """Handle validate-only runs without invoking the engine."""

        logger.info(
            "run.validate_only.start",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
            ),
        )
        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )
        completion = await self._complete_run_if_owned(
            run=run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
            error_message=None,
            worker_id=worker_id,
        )
        if completion is None:
            return
        yield await self._emit_api_event(
            run=completion,
            type_="run.complete",
            payload=self._run_completed_payload(
                run=completion,
                paths=paths_snapshot,
                failure_message="Validation-only execution",
            ),
        )
        logger.info(
            "run.validate_only.completed",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
            ),
        )

    async def _stream_safe_mode_skip(
        self,
        *,
        run: Run,
        mode_literal: str,
        safe_mode: SafeModeStatus,
        worker_id: str,
    ) -> AsyncIterator[RunStreamFrame]:
        """Handle safe-mode runs by skipping engine execution."""

        logger.info(
            "run.safe_mode.skip.start",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                safe_mode_enabled=True,
                safe_mode_detail=safe_mode.detail,
            ),
        )

        message = f"Safe mode enabled: {safe_mode.detail}"
        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )
        completion = await self._complete_run_if_owned(
            run=run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
            error_message=None,
            worker_id=worker_id,
        )
        if completion is None:
            return

        # Console notification
        yield await self._emit_api_event(
            run=run,
            type_="console.line",
            payload={
                "scope": "run",
                "stream": "stdout",
                "level": "info",
                "message": message,
            },
        )

        # Completion event
        yield await self._emit_api_event(
            run=completion,
            type_="run.complete",
            payload=self._run_completed_payload(
                run=completion,
                paths=paths_snapshot,
                failure_message=message,
            ),
        )

        logger.info(
            "run.safe_mode.skip.completed",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
            ),
        )

    async def _stream_engine_run(
        self,
        *,
        run: Run,
        context: RunExecutionContext,
        options: RunCreateOptions,
        mode_literal: str,
        safe_mode_enabled: bool,
        worker_id: str,
    ) -> AsyncIterator[RunStreamFrame]:
        """Wrap `_execute_engine` with supervision and event translation."""

        async def generator() -> AsyncIterator[RunStreamFrame]:
            async for frame in self._execute_engine(
                run=run,
                context=context,
                options=options,
                safe_mode_enabled=safe_mode_enabled,
            ):
                yield frame

        logger.debug(
            "run.engine.stream.start",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                safe_mode_enabled=safe_mode_enabled,
            ),
        )

        run_stream = self._event_stream_for_run(run)

        try:
            async for frame in self._supervisor.stream(
                run.id,
                generator=generator,
            ):
                # Final result from _execute_engine
                if isinstance(frame, RunExecutionResult):
                    paths_snapshot = frame.paths_snapshot or RunPathsSnapshot()

                    if frame.status is RunStatus.FAILED:
                        retried = await self._maybe_retry_run(
                            run=run,
                            worker_id=worker_id,
                            error_message=frame.error_message,
                        )
                        if retried:
                            logger.info(
                                "run.retry.scheduled",
                                extra=log_context(
                                    workspace_id=run.workspace_id,
                                    configuration_id=run.configuration_id,
                                    run_id=run.id,
                                    attempt_count=run.attempt_count + 1,
                                ),
                            )
                            return

                    completion = await self._complete_run_if_owned(
                        run=run,
                        status=frame.status,
                        exit_code=frame.return_code,
                        error_message=frame.error_message,
                        worker_id=worker_id,
                    )
                    if completion is None:
                        return
                    event = await self._emit_api_event(
                        run=completion,
                        type_="run.complete",
                        payload=self._run_completed_payload(
                            run=completion,
                            paths=paths_snapshot,
                            failure_stage=("run" if frame.status is RunStatus.FAILED else None),
                            failure_message=frame.error_message,
                        ),
                    )
                    self._log_event_debug(event, origin="api")
                    yield event
                    continue

                # Stdout/stderr line from the engine
                if isinstance(frame, StdoutFrame):
                    parsed = None
                    if frame.stream == "stderr":
                        parsed = coerce_event_record(frame.message)
                    if parsed:
                        forwarded = await run_stream.append(parsed)
                        self._log_event_debug(forwarded, origin="engine")
                        await self._handle_engine_event(run=run, event=forwarded)
                        yield forwarded
                        continue

                    forwarded = await self._emit_engine_console_line(
                        run=run,
                        frame=frame,
                    )
                    self._log_event_debug(forwarded, origin="engine")
                    yield forwarded
                    continue

        except asyncio.CancelledError:
            logger.warning(
                "run.engine.stream.cancelled",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                ),
            )
            run_dir = self._run_dir_for_run(
                workspace_id=run.workspace_id,
                run_id=run.id,
            )
            paths_snapshot = self._finalize_paths(
                run_dir=run_dir,
                default_paths=RunPathsSnapshot(),
            )
            completion = await self._complete_run_if_owned(
                run=run,
                status=RunStatus.CANCELLED,
                exit_code=None,
                error_message="Run execution cancelled",
                worker_id=worker_id,
            )
            if completion is not None:
                event = await self._emit_api_event(
                    run=completion,
                    type_="run.complete",
                    payload=self._run_completed_payload(
                        run=completion,
                        paths=paths_snapshot,
                        failure_stage="run",
                        failure_code="run_cancelled",
                        failure_message=completion.error_message,
                    ),
                )
                self._log_event_debug(event, origin="api")
                yield event
            raise

        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "run.engine.stream.error",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                ),
            )
            run_dir = self._run_dir_for_run(
                workspace_id=run.workspace_id,
                run_id=run.id,
            )
            paths_snapshot = self._finalize_paths(
                run_dir=run_dir,
                default_paths=RunPathsSnapshot(),
            )
            retried = await self._maybe_retry_run(
                run=run,
                worker_id=worker_id,
                error_message=str(exc),
            )
            if retried:
                logger.info(
                    "run.retry.scheduled",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                        attempt_count=run.attempt_count + 1,
                    ),
                )
                return
            completion = await self._complete_run_if_owned(
                run=run,
                status=RunStatus.FAILED,
                exit_code=None,
                error_message=str(exc),
                worker_id=worker_id,
            )
            if completion is None:
                return
            # Error console frame
            console_event = await self._emit_api_event(
                run=run,
                type_="console.line",
                payload={
                    "scope": "run",
                    "stream": "stderr",
                    "level": "error",
                    "message": f"ADE run failed: {exc}",
                },
            )
            self._log_event_debug(console_event, origin="api")
            yield console_event

            # Run completion frame
            complete_event = await self._emit_api_event(
                run=completion,
                type_="run.complete",
                payload=self._run_completed_payload(
                    run=completion,
                    paths=paths_snapshot,
                    failure_stage="run",
                    failure_code="engine_error",
                    failure_message=completion.error_message,
                ),
            )
            self._log_event_debug(complete_event, origin="api")
            yield complete_event
            return

    # --------------------------------------------------------------------- #
    # Internal helpers: DB, storage, builds
    # --------------------------------------------------------------------- #

    async def _require_run(self, run_id: UUID) -> Run:
        run = await self._runs.get(run_id)
        if run is None:
            logger.warning(
                "run.require_run.not_found",
                extra=log_context(run_id=run_id),
            )
            raise RunNotFoundError(run_id)
        return run

    async def _require_document(self, *, workspace_id: UUID, document_id: UUID) -> Document:
        document = await self._documents.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        if document is None:
            logger.warning(
                "run.require_document.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=document_id,
                ),
            )
            raise RunDocumentMissingError(f"Document {document_id} not found")
        return document

    async def _require_documents(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
    ) -> list[Document]:
        if not document_ids:
            return []

        stmt = select(Document).where(
            Document.workspace_id == workspace_id,
            Document.deleted_at.is_(None),
            Document.id.in_(document_ids),
        )
        result = await self._session.execute(stmt)
        documents = list(result.scalars())
        found = {doc.id for doc in documents}
        missing = [document_id for document_id in document_ids if document_id not in found]
        if missing:
            logger.warning(
                "run.require_documents.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=str(missing[0]),
                    missing_count=len(missing),
                ),
            )
            raise RunDocumentMissingError(f"Document {missing[0]} not found")
        return documents

    def _storage_for(self, workspace_id: UUID) -> DocumentStorage:
        base = workspace_documents_root(self._settings, workspace_id)
        return DocumentStorage(base)

    async def _stage_input_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        run_dir: Path,
    ) -> Path:
        document = await self._require_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        storage = self._storage_for(workspace_id)

        return await stage_document_input(
            document=document,
            storage=storage,
            session=self._session,
            run_dir=run_dir,
        )

    async def _resolve_configuration(self, configuration_id: UUID) -> Configuration:
        configuration = await self._configs.get_by_id(configuration_id)
        if configuration is None:
            logger.warning(
                "run.config.resolve.not_found",
                extra=log_context(configuration_id=configuration_id),
            )
            raise ConfigurationNotFoundError(configuration_id)
        if configuration.status == ConfigurationStatus.ARCHIVED:
            logger.warning(
                "run.config.resolve.archived",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    status=configuration.status.value,
                ),
            )
        return configuration

    async def _processing_paused(self, workspace_id: UUID) -> bool:
        workspace = await self._workspaces.get_workspace(workspace_id)
        if workspace is None:
            return False
        return read_processing_paused(workspace.settings)

    async def _resolve_workspace_configuration(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID | None,
    ) -> Configuration:
        if configuration_id is None:
            configuration = await self._configs.get_active(workspace_id)
            if configuration is None:
                logger.warning(
                    "run.config.resolve.active_missing",
                    extra=log_context(workspace_id=workspace_id),
                )
                raise ConfigurationNotFoundError("active_configuration_not_found")
        else:
            configuration = await self._configs.get(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
            )
            if configuration is None:
                logger.warning(
                    "run.config.resolve.not_found",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                    ),
                )
                raise ConfigurationNotFoundError(configuration_id)

        if configuration.status == ConfigurationStatus.ARCHIVED:
            logger.warning(
                "run.config.resolve.archived",
                extra=log_context(
                    workspace_id=configuration.workspace_id,
                    configuration_id=configuration.id,
                    status=configuration.status.value,
                ),
            )
        return configuration

    async def _emit_document_upsert(self, document: Document) -> None:
        payload = DocumentOut.model_validate(document)
        await self._documents_service._attach_last_runs(document.workspace_id, [payload])
        queue_context = await self._documents_service.build_queue_context(
            workspace_id=document.workspace_id,
        )
        self._documents_service._apply_derived_fields(payload, queue_context)
        await self._document_changes.record_upsert(
            workspace_id=document.workspace_id,
            document_id=document.id,
            payload=payload.model_dump(),
        )
        await self._session.commit()

    async def _touch_document_status(
        self,
        *,
        run: Run,
        status: DocumentStatus,
    ) -> Document | None:
        if not run.input_document_id:
            return None
        document = await self._documents.get_document(
            workspace_id=run.workspace_id,
            document_id=run.input_document_id,
            include_deleted=True,
        )
        if document is None or document.status == DocumentStatus.ARCHIVED:
            return None
        if document.status == status:
            return document
        document.status = status
        await self._session.flush()
        return document

    async def _complete_run_if_owned(
        self,
        *,
        run: Run,
        status: RunStatus,
        exit_code: int | None,
        error_message: str | None,
        worker_id: str,
    ) -> Run | None:
        now = utc_now()
        values: dict[str, Any] = {
            "status": status,
            "exit_code": exit_code,
            "completed_at": now,
            "cancelled_at": now if status is RunStatus.CANCELLED else None,
            "claimed_by": None,
            "claim_expires_at": None,
            "error_message": error_message,
        }

        stmt = (
            update(Run)
            .where(
                Run.id == run.id,
                Run.status == RunStatus.RUNNING,
                Run.claimed_by == worker_id,
            )
            .values(**values)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        if not result.rowcount:
            logger.warning(
                "run.complete.claim_lost",
                extra=log_context(run_id=run.id),
            )
            return None

        refreshed = await self._runs.get(run.id)
        if refreshed is None:
            return None

        await self._finalize_completion_side_effects(run=refreshed)
        return refreshed

    async def _complete_run(
        self,
        run: Run,
        *,
        status: RunStatus,
        exit_code: int | None,
        error_message: str | None = None,
    ) -> Run:
        run.status = status
        run.exit_code = exit_code
        run.error_message = error_message
        run.completed_at = utc_now()
        run.cancelled_at = utc_now() if status is RunStatus.CANCELLED else None
        run.claimed_by = None
        run.claim_expires_at = None
        await self._session.commit()
        await self._session.refresh(run)

        await self._finalize_completion_side_effects(run=run)
        return run

    async def _finalize_completion_side_effects(self, *, run: Run) -> None:
        document = None
        if run.status is RunStatus.SUCCEEDED:
            document = await self._touch_document_status(
                run=run,
                status=DocumentStatus.PROCESSED,
            )
        elif run.status is RunStatus.FAILED or run.status is RunStatus.CANCELLED:
            document = await self._touch_document_status(
                run=run,
                status=DocumentStatus.FAILED,
            )
        if document is not None:
            await self._session.commit()
            await self._emit_document_upsert(document)

        await self._ensure_terminal_metrics_stub(run=run)
        await self._maybe_enqueue_pending_runs(workspace_id=run.workspace_id)

        logger.info(
            "run.complete",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                status=run.status.value,
                exit_code=run.exit_code,
                has_error=bool(run.error_message),
            ),
        )

    async def _ensure_terminal_metrics_stub(self, *, run: Run) -> None:
        if run.status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
            return
        existing = await self._session.get(RunMetrics, run.id)
        if existing is not None:
            return
        outcome = "failure" if run.status is RunStatus.FAILED else "unknown"
        self._session.add(
            RunMetrics(
                run_id=run.id,
                evaluation_outcome=outcome,
            )
        )
        await self._session.commit()

    @staticmethod
    def _build_env(
        venv_path: Path,
        options: RunCreateOptions,
        context: RunExecutionContext,
        *,
        input_sheet_name: str | None = None,
    ) -> dict[str, str]:
        env = apply_venv_to_env(os.environ, venv_path)
        if options.dry_run:
            env["ADE_RUN_DRY_RUN"] = "1"
        if options.validate_only:
            env["ADE_RUN_VALIDATE_ONLY"] = "1"
        sheet_name = input_sheet_name
        if sheet_name:
            env["ADE_RUN_INPUT_SHEET"] = sheet_name
        if context.run_id:
            env["ADE_TELEMETRY_CORRELATION_ID"] = str(context.run_id)
            env["ADE_RUN_ID"] = str(context.run_id)
        return env

    def _run_dir_for_run(self, *, workspace_id: UUID, run_id: UUID) -> Path:
        root = workspace_run_root(self._settings, workspace_id).resolve()
        candidate = (root / str(run_id)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:  # pragma: no cover - defensive guard
            logger.warning(
                "run.directory.escape_detected",
                extra=log_context(workspace_id=workspace_id, run_id=run_id, path=str(candidate)),
            )
            raise RunOutputMissingError("Requested path escapes runs directory") from None
        return candidate

    @staticmethod
    def _epoch_seconds(dt: datetime | None) -> int | None:
        if dt is None:
            return None
        return int(dt.timestamp())

    @staticmethod
    def _duration_ms(run: Run) -> int | None:
        if run.started_at and run.completed_at:
            return int((run.completed_at - run.started_at).total_seconds() * 1000)
        return None

    @staticmethod
    def _format_mode_message(options: RunCreateOptions) -> str | None:
        """Render a one-line banner describing special run modes, if any."""

        modes: list[str] = []
        if options.dry_run:
            modes.append("dry-run enabled")
        if options.validate_only:
            modes.append("validate-only mode")
        if getattr(options, "active_sheet_only", False):
            modes.append("active-sheet-only")
        if not modes:
            return None
        return "Run options: " + ", ".join(modes)

    @staticmethod
    def _merge_run_options(
        *,
        input_document_id: UUID,
        options: RunCreateOptionsBase | None,
    ) -> RunCreateOptions:
        payload = options.model_dump(exclude_none=True) if options else {}
        return RunCreateOptions(input_document_id=input_document_id, **payload)

    async def _safe_mode_status(self) -> SafeModeStatus:
        if self._safe_mode_service is not None:
            return await self._safe_mode_service.get_status()
        return SafeModeStatus(
            enabled=self._settings.safe_mode,
            detail=SAFE_MODE_DEFAULT_DETAIL,
        )

    @staticmethod
    def _select_input_sheet_names(options: RunCreateOptions) -> list[str]:
        """Normalize requested sheet names into a unique, ordered list."""

        if getattr(options, "active_sheet_only", False):
            return []
        names: list[str] = []
        for name in getattr(options, "input_sheet_names", None) or []:
            if not isinstance(name, str):
                continue
            cleaned = name.strip()
            if cleaned and cleaned not in names:
                names.append(cleaned)
        return names

    @staticmethod
    def _select_input_sheet_name(options: RunCreateOptions) -> str | None:
        """Resolve the first selected sheet name from the run options, if any."""

        if getattr(options, "active_sheet_only", False):
            return None
        normalized = RunsService._select_input_sheet_names(options)
        return normalized[0] if normalized else None

    # ------------------------------------------------------------------ #
    # Internal helpers: event streams
    # ------------------------------------------------------------------ #

    def _event_context(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        configuration_id: UUID,
        build_id: UUID | None,
    ) -> RunEventContext:
        return RunEventContext(
            job_id=str(run_id),
            workspace_id=str(workspace_id),
            build_id=str(build_id) if build_id else None,
            configuration_id=str(configuration_id),
        )

    def _event_stream_for_run(self, run: Run) -> RunEventStream:
        return self._event_stream_for_ids(
            workspace_id=run.workspace_id,
            run_id=run.id,
            configuration_id=run.configuration_id,
            build_id=getattr(run, "build_id", None),
        )

    def _event_stream_for_ids(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        configuration_id: UUID,
        build_id: UUID | None,
    ) -> RunEventStream:
        run_dir = self._run_dir_for_run(workspace_id=workspace_id, run_id=run_id)
        path = run_dir / "logs" / "events.ndjson"
        context = self._event_context(
            workspace_id=workspace_id,
            run_id=run_id,
            configuration_id=configuration_id,
            build_id=build_id,
        )
        return self._event_streams.get_stream(path=path, context=context)

    # ------------------------------------------------------------------ #
    # Internal helpers: run metrics
    # ------------------------------------------------------------------ #

    async def _handle_engine_event(self, *, run: Run, event: EventRecord) -> None:
        """Handle engine events that require persistence side effects."""

        payload = self._parse_run_completed_payload(event)
        if payload is None:
            return

        metrics, fields, columns = self._extract_run_completed(payload)
        await self._persist_run_completed(
            run_id=run.id,
            metrics=metrics,
            fields=fields,
            columns=columns,
        )

    @staticmethod
    def _parse_run_completed_payload(event: EventRecord) -> dict[str, Any] | None:
        if event.get("event") != "engine.run.completed":
            return None
        payload = event.get("data")
        if not isinstance(payload, dict):
            return None
        return payload

    def _extract_run_completed(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        metrics = self._extract_run_metrics(payload)
        fields = self._extract_run_fields(self._as_list(payload.get("fields")) or [])
        columns = self._extract_run_columns(self._as_list(payload.get("workbooks")) or [])
        return metrics, fields, columns

    async def _persist_run_completed(
        self,
        *,
        run_id: UUID,
        metrics: dict[str, Any],
        fields: list[dict[str, Any]],
        columns: list[dict[str, Any]],
    ) -> None:
        existing = await self._session.get(RunMetrics, run_id)
        if existing is None:
            self._session.add(RunMetrics(run_id=run_id, **metrics))
        else:
            for key, value in metrics.items():
                setattr(existing, key, value)

        if fields:
            exists_stmt = select(RunField.run_id).where(RunField.run_id == run_id).limit(1)
            result = await self._session.execute(exists_stmt)
            if not result.first():
                self._session.add_all([RunField(run_id=run_id, **row) for row in fields])

        if columns:
            exists_stmt = (
                select(RunTableColumn.run_id)
                .where(RunTableColumn.run_id == run_id)
                .limit(1)
            )
            result = await self._session.execute(exists_stmt)
            if not result.first():
                self._session.add_all(
                    [RunTableColumn(run_id=run_id, **row) for row in columns]
                )

        await self._session.commit()

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _as_list(value: Any) -> list[Any] | None:
        return value if isinstance(value, list) else None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None

    @staticmethod
    def _coerce_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _extract_run_metrics(payload: dict[str, Any]) -> dict[str, Any]:
        evaluation = RunsService._as_dict(payload.get("evaluation"))
        findings = RunsService._as_list(evaluation.get("findings"))
        findings_total = len(findings) if isinstance(findings, list) else None
        findings_by_severity = {"info": 0, "warning": 0, "error": 0}
        for finding in findings or []:
            if not isinstance(finding, dict):
                continue
            severity = finding.get("severity")
            if severity in findings_by_severity:
                findings_by_severity[severity] += 1

        validation = RunsService._as_dict(payload.get("validation"))
        issues_by_severity = RunsService._as_dict(validation.get("issues_by_severity"))
        issues_info = RunsService._coerce_int(issues_by_severity.get("info"))
        issues_warning = RunsService._coerce_int(issues_by_severity.get("warning"))
        issues_error = RunsService._coerce_int(issues_by_severity.get("error"))

        counts = RunsService._as_dict(payload.get("counts"))
        rows = RunsService._as_dict(counts.get("rows"))
        columns = RunsService._as_dict(counts.get("columns"))
        fields = RunsService._as_dict(counts.get("fields"))
        cells = RunsService._as_dict(counts.get("cells"))

        columns_mapped = RunsService._coerce_int(columns.get("mapped"))
        columns_unmapped = RunsService._coerce_int(columns.get("unmapped"))
        field_count_detected = RunsService._coerce_int(fields.get("detected"))
        field_count_not_detected = RunsService._coerce_int(fields.get("not_detected"))

        return {
            "evaluation_outcome": RunsService._coerce_str(evaluation.get("outcome")),
            "evaluation_findings_total": findings_total,
            "evaluation_findings_info": (
                findings_by_severity["info"] if findings_total is not None else None
            ),
            "evaluation_findings_warning": (
                findings_by_severity["warning"] if findings_total is not None else None
            ),
            "evaluation_findings_error": (
                findings_by_severity["error"] if findings_total is not None else None
            ),
            "validation_issues_total": RunsService._coerce_int(validation.get("issues_total")),
            "validation_issues_info": issues_info,
            "validation_issues_warning": issues_warning,
            "validation_issues_error": issues_error,
            "validation_max_severity": RunsService._coerce_str(validation.get("max_severity")),
            "workbook_count": RunsService._coerce_int(counts.get("workbooks")),
            "sheet_count": RunsService._coerce_int(counts.get("sheets")),
            "table_count": RunsService._coerce_int(counts.get("tables")),
            "row_count_total": RunsService._coerce_int(rows.get("total")),
            "row_count_empty": RunsService._coerce_int(rows.get("empty")),
            "column_count_total": RunsService._coerce_int(columns.get("total")),
            "column_count_empty": RunsService._coerce_int(columns.get("empty")),
            "column_count_mapped": columns_mapped,
            "column_count_unmapped": columns_unmapped,
            "field_count_expected": RunsService._coerce_int(fields.get("expected")),
            "field_count_detected": field_count_detected,
            "field_count_not_detected": field_count_not_detected,
            "cell_count_total": RunsService._coerce_int(cells.get("total")),
            "cell_count_non_empty": RunsService._coerce_int(cells.get("non_empty")),
        }

    @staticmethod
    def _extract_run_fields(fields_payload: list[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for entry in fields_payload:
            if not isinstance(entry, dict):
                continue
            field_name = RunsService._coerce_str(entry.get("field"))
            if not field_name or field_name in seen:
                continue
            seen.add(field_name)

            occurrences = entry.get("occurrences")
            if not isinstance(occurrences, dict):
                occurrences = {}

            rows.append(
                {
                    "field": field_name,
                    "label": RunsService._coerce_str(entry.get("label")),
                    "detected": True if entry.get("detected") is True else False,
                    "best_mapping_score": RunsService._coerce_float(
                        entry.get("best_mapping_score")
                    ),
                    "occurrences_tables": RunsService._coerce_int(occurrences.get("tables")) or 0,
                    "occurrences_columns": RunsService._coerce_int(occurrences.get("columns")) or 0,
                }
            )

        return rows

    @staticmethod
    def _extract_run_columns(workbooks: list[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for workbook in workbooks:
            if not isinstance(workbook, dict):
                continue
            locator = workbook.get("locator")
            if not isinstance(locator, dict):
                continue
            wb_locator = locator.get("workbook")
            if not isinstance(wb_locator, dict):
                continue
            workbook_index = RunsService._coerce_int(wb_locator.get("index"))
            workbook_name = RunsService._coerce_str(wb_locator.get("name"))
            if workbook_index is None or workbook_name is None:
                continue

            sheets = workbook.get("sheets")
            if not isinstance(sheets, list):
                continue

            for sheet in sheets:
                if not isinstance(sheet, dict):
                    continue
                sheet_locator = sheet.get("locator")
                if not isinstance(sheet_locator, dict):
                    continue
                sheet_ref = sheet_locator.get("sheet")
                if not isinstance(sheet_ref, dict):
                    continue
                sheet_index = RunsService._coerce_int(sheet_ref.get("index"))
                sheet_name = RunsService._coerce_str(sheet_ref.get("name"))
                if sheet_index is None or sheet_name is None:
                    continue

                tables = sheet.get("tables")
                if not isinstance(tables, list):
                    continue

                for table in tables:
                    if not isinstance(table, dict):
                        continue
                    table_locator = table.get("locator")
                    if not isinstance(table_locator, dict):
                        continue
                    table_ref = table_locator.get("table")
                    if not isinstance(table_ref, dict):
                        continue
                    table_index = RunsService._coerce_int(table_ref.get("index"))
                    if table_index is None:
                        continue

                    structure = table.get("structure")
                    if not isinstance(structure, dict):
                        continue
                    columns = structure.get("columns")
                    if not isinstance(columns, list):
                        continue

                    for column in columns:
                        if not isinstance(column, dict):
                            continue
                        column_index = RunsService._coerce_int(column.get("index"))
                        if column_index is None:
                            continue
                        header = column.get("header")
                        header_raw = None
                        header_normalized = None
                        if isinstance(header, dict):
                            header_raw = RunsService._coerce_str(header.get("raw"))
                            header_normalized = RunsService._coerce_str(header.get("normalized"))
                        non_empty_cells = RunsService._coerce_int(column.get("non_empty_cells"))
                        if non_empty_cells is None:
                            continue
                        mapping = column.get("mapping")
                        if not isinstance(mapping, dict):
                            continue
                        mapping_status = RunsService._coerce_str(mapping.get("status"))
                        if mapping_status is None:
                            continue
                        mapping_status = mapping_status.lower()
                        if mapping_status not in {"mapped", "unmapped"}:
                            continue

                        rows.append(
                            {
                                "workbook_index": workbook_index,
                                "workbook_name": workbook_name,
                                "sheet_index": sheet_index,
                                "sheet_name": sheet_name,
                                "table_index": table_index,
                                "column_index": column_index,
                                "header_raw": header_raw,
                                "header_normalized": header_normalized,
                                "non_empty_cells": non_empty_cells,
                                "mapping_status": mapping_status,
                                "mapped_field": RunsService._coerce_str(mapping.get("field")),
                                "mapping_score": RunsService._coerce_float(mapping.get("score")),
                                "mapping_method": RunsService._coerce_str(mapping.get("method")),
                                "unmapped_reason": RunsService._coerce_str(mapping.get("unmapped_reason")),
                            }
                        )

        return rows

    # ------------------------------------------------------------------ #
    # Internal helpers: event logging
    # ------------------------------------------------------------------ #

    @staticmethod
    def _log_event_debug(event: EventRecord, *, origin: str) -> None:
        """Emit events to the console when debug logging is enabled."""

        if not event_logger.isEnabledFor(logging.DEBUG):
            return

        event_logger.debug(
            "[%s] %s %s",
            origin,
            event.get("event"),
            json.dumps(event, default=str),
        )

    async def _emit_engine_console_line(self, *, run: Run, frame: StdoutFrame) -> EventRecord:
        """Coerce stdout/stderr lines into canonical console events."""

        level = "warning" if frame.stream == "stderr" else "info"
        event = new_event_record(
            event="console.line",
            message=frame.message,
            level=level,
            data={
                "scope": "run",
                "stream": frame.stream,
                "level": level,
                "message": frame.message,
            },
        )
        stream = self._event_stream_for_run(run)
        appended = await stream.append(event)
        self._log_event_debug(appended, origin="engine")
        return appended

    async def _emit_api_event(
        self,
        *,
        run: Run,
        type_: str,
        payload: dict[str, Any] | Any | None = None,
        build_id: UUID | None = None,
        level: str = "info",
        message: str | None = None,
    ) -> EventRecord:
        """Emit an EventRecord originating from the API orchestrator."""

        build_identifier = build_id or getattr(run, "build_id", None)
        stream = self._event_stream_for_run(run)
        payload_dict: dict[str, Any] = {}
        if payload is not None:
            if hasattr(payload, "model_dump"):
                payload_dict = payload.model_dump(exclude_none=True)  # type: ignore[assignment]
            elif isinstance(payload, dict):
                payload_dict = payload
            else:
                payload_dict = dict(payload)
        if build_identifier:
            payload_dict.setdefault("build_id", str(build_identifier))
        event = new_event_record(
            event=type_,
            message=message,
            level=level,
            data=payload_dict,
        )
        appended = await stream.append(event)
        self._log_event_debug(appended, origin="api")
        return appended

    async def _ensure_run_queued_event(
        self,
        *,
        run: Run,
        mode_literal: str,
        options: RunCreateOptions,
    ) -> EventRecord | None:
        """Guarantee a single run.queued event exists for the run."""

        stream = self._event_stream_for_run(run)
        if stream.last_cursor() > 0:
            return next(iter(stream.iter_persisted(after_sequence=0)), None)
        return await self._emit_api_event(
            run=run,
            type_="run.queued",
            payload={
                "status": "queued",
                "mode": mode_literal,
                "options": options.model_dump(mode="json", exclude_none=True),
            },
        )

    def iter_events(self, *, run: Run, after_sequence: int | None = None):
        """Yield persisted events for a run."""

        return self._event_stream_for_run(run).iter_persisted(after_sequence=after_sequence)

    def subscribe_to_events(self, run: Run):
        """Expose subscription for live event streaming."""

        return self._event_stream_for_run(run).subscribe()

    @property
    def settings(self) -> Settings:
        """Expose the bound settings instance for caller reuse."""

        return self._settings
