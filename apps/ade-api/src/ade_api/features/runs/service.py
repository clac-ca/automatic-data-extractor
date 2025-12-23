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

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.events import (
    EventRecord,
    coerce_event_record,
    new_event_record,
)
from ade_api.common.ids import generate_uuid7
from ade_api.common.logging import log_context
from ade_api.common.pagination import Page
from ade_api.common.time import utc_now
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.documents.repository import DocumentsRepository
from ade_api.features.documents.staging import stage_document_input
from ade_api.features.documents.storage import DocumentStorage
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
    Run,
    RunStatus,
)
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
from .repository import RunsRepository
from .runner import EngineSubprocessRunner, StdoutFrame
from .schemas import (
    RunCreateOptions,
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
    summary_model: Any | None = None
    summary_json: str | None = None


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

        self._session = session
        self._settings = settings
        self._configs = ConfigurationsRepository(session)
        self._runs = RunsRepository(session)
        self._supervisor = supervisor or RunExecutionSupervisor()
        self._documents = DocumentsRepository(session)
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

        if settings.documents_dir is None:
            raise RuntimeError("ADE_DOCUMENTS_DIR is not configured")
        if settings.runs_dir is None:
            raise RuntimeError("ADE_RUNS_DIR is not configured")

        self._runs_dir = Path(settings.runs_dir)

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

        run_id = self._generate_run_id()

        build, _ = await self._builds_service.ensure_build_for_run(
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            force_rebuild=options.force_rebuild,
            run_id=run_id,
            reason="on_demand",
        )
        build_id = build.id
        if build.status is not BuildStatus.READY:
            await self._builds_service.launch_build_if_needed(
                build=build,
                reason="run_requested",
                run_id=run_id,
            )

        await self._enforce_queue_capacity()

        selected_sheet_names = self._select_input_sheet_names(options)

        run = Run(
            id=run_id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            status=RunStatus.QUEUED,
            trace_id=str(run_id),
            input_document_id=input_document_id,
            input_sheet_names=selected_sheet_names or None,
            build_id=build_id,
        )
        self._session.add(run)

        # Touch configuration usage timestamp.
        configuration.last_used_at = utc_now()  # type: ignore[attr-defined]

        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(run)

        mode_literal = "validate" if options.validate_only else "execute"
        await self._emit_api_event(
            run=run,
            type_="run.queued",
            payload={
                "status": "queued",
                "mode": mode_literal,
                "options": options.model_dump(exclude_none=True),
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

    async def load_run_options(self, run: Run) -> RunCreateOptions:
        """Rehydrate run options from the persisted run.queued event."""

        payload: dict[str, Any] = {}
        stream = self._event_stream_for_run(run)
        try:
            for event in stream.iter_persisted(after_sequence=0):
                if event.get("event") == "run.queued":
                    payload = (event.get("data") or {}).get("options") or {}
                    break
        except Exception:
            payload = {}

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

    async def claim_next_run(self) -> Run | None:
        candidate = await self._runs.next_queued_with_terminal_build()
        if candidate is None:
            return None
        run, build_status = candidate
        if build_status in (BuildStatus.FAILED, BuildStatus.CANCELLED):
            build = await self._builds_service.get_build_or_raise(
                run.build_id,
                workspace_id=run.workspace_id,
            )
            async for _ in self._fail_run_due_to_build(run=run, build=build):
                pass
            return None

        claimed = await self._claim_run(run.id)
        if not claimed:
            return None
        return await self._require_run(run.id)

    async def expire_stuck_runs(self) -> int:
        timeout_seconds = self._settings.run_timeout_seconds
        if not timeout_seconds:
            return 0
        horizon = utc_now() - timedelta(seconds=timeout_seconds)
        stmt = (
            select(Run)
            .where(
                Run.status == RunStatus.RUNNING,
                Run.started_at.is_not(None),
                Run.started_at < horizon,
            )
            .order_by(Run.started_at.asc())
        )
        result = await self._session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0

        message = f"Run timed out after {timeout_seconds}s"
        for run in runs:
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
                    failure_code="run_timeout",
                    failure_message=message,
                ),
            )

        logger.warning(
            "run.stuck.expired",
            extra=log_context(count=len(runs), timeout_seconds=timeout_seconds),
        )
        return len(runs)

    async def expire_stuck_builds(self) -> int:
        return await self._builds_service.expire_stuck_builds()

    async def _enforce_queue_capacity(self) -> None:
        limit = self._settings.queue_size
        if not limit:
            return
        queued = await self._runs.count_queued()
        if queued >= limit:
            raise RunQueueFullError(f"Run queue is full (limit {limit})")

    async def _claim_run(self, run_id: UUID) -> bool:
        stmt = (
            update(Run)
            .where(Run.id == run_id, Run.status == RunStatus.QUEUED)
            .values(status=RunStatus.RUNNING, started_at=utc_now())
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return bool(result.rowcount)

    async def _requeue_run(self, run: Run, *, reason: str) -> Run:
        run.status = RunStatus.QUEUED
        run.started_at = None
        await self._session.commit()
        await self._session.refresh(run)
        logger.info(
            "run.requeued",
            extra=log_context(run_id=run.id, reason=reason),
        )
        return run

    async def _fail_run_due_to_build(
        self,
        *,
        run: Run,
        build: Build,
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
        completion = await self._complete_run(
            run,
            status=RunStatus.FAILED,
            exit_code=1,
            error_message=error_message,
        )
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
    ) -> None:
        """Execute the run, exhausting the event stream."""

        if options is None:
            run = await self._require_run(run_id)
            options = await self.load_run_options(run)

        logger.info(
            "run.execute.start",
            extra=log_context(
                run_id=run_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )
        async for _ in self.stream_run(run_id=run_id, options=options):
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
    ) -> AsyncIterator[RunStreamFrame]:
        """Iterate through run events while executing the engine."""

        context = await self._execution_context_for_run(run_id)
        logger.debug(
            "run.stream.start",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                run_id=context.run_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )

        try:
            async for event in self._stream_run_steps(context=context, options=options):
                yield event
        except Exception as exc:  # pragma: no cover - defensive orchestration guard
            async for event in self._handle_stream_failure(
                context=context,
                options=options,
                error=exc,
            ):
                yield event

    async def _stream_run_steps(
        self,
        *,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> AsyncIterator[RunStreamFrame]:
        """Orchestrate run execution and yield events; raised exceptions are handled upstream."""

        run = await self._require_run(context.run_id)
        mode_literal = "validate" if options.validate_only else "execute"

        queued_event = await self._ensure_run_queued_event(
            run=run,
            mode_literal=mode_literal,
            options=options,
        )
        if queued_event:
            yield queued_event

        build = await self._builds_service.get_build_or_raise(
            context.build_id,
            workspace_id=context.workspace_id,
        )
        if build.status in (BuildStatus.FAILED, BuildStatus.CANCELLED):
            async for event in self._fail_run_due_to_build(run=run, build=build):
                yield event
            return
        if build.status is not BuildStatus.READY:
            await self._requeue_run(run, reason="build_not_ready")
            return

        run = await self._transition_status(run, RunStatus.RUNNING)
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
            async for event in self._stream_validate_only_run(run=run, mode_literal=mode_literal):
                yield event
            return

        # Safe mode short circuit: log the skip and exit.
        if safe_mode.enabled:
            async for event in self._stream_safe_mode_skip(
                run=run,
                mode_literal=mode_literal,
                safe_mode=safe_mode,
            ):
                yield event
            return

        # Full engine execution: delegate to the process runner + supervisor.
        async for event in self._stream_engine_run(
            run=run,
            context=context,
            options=options,
            mode_literal=mode_literal,
            safe_mode_enabled=safe_mode.enabled,
        ):
            yield event

    async def _handle_stream_failure(
        self,
        *,
        context: RunExecutionContext,
        options: RunCreateOptions,
        error: Exception,
    ) -> AsyncIterator[RunStreamFrame]:
        """Emit console + completion events when unexpected orchestration errors occur."""

        logger.exception(
            "run.stream.unhandled_error",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                run_id=context.run_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
            exc_info=error,
        )

        run = await self._runs.get(context.run_id)
        if run is None:
            return
        if run.status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED):
            return

        message = f"ADE run orchestration failed: {error}"
        yield await self._emit_api_event(
            run=run,
            type_="console.line",
            payload={
                "scope": "run",
                "stream": "stderr",
                "level": "error",
                "message": message,
            },
        )

        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
        paths_snapshot = self._finalize_paths(
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )
        completion = await self._complete_run(
            run,
            status=RunStatus.FAILED,
            exit_code=None,
            error_message=str(error),
        )
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

        try:
            context = await self._execution_context_for_run(run_id)
        except Exception:
            return

        async for event in self._handle_stream_failure(
            context=context,
            options=options,
            error=error,
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
        statuses: Sequence[RunStatus] | None,
        input_document_id: UUID | None,
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
                statuses=[s.value for s in statuses] if statuses else None,
                input_document_id=input_document_id,
                page=page,
                page_size=page_size,
                include_total=include_total,
            ),
        )

        page_result = await self._runs.list_by_workspace(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            statuses=statuses,
            input_document_id=input_document_id,
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
        statuses: Sequence[RunStatus] | None,
        input_document_id: UUID | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[RunResource]:
        """Return paginated runs for ``configuration_id`` scoped to its workspace."""

        configuration = await self._resolve_configuration(configuration_id)
        return await self.list_runs(
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            statuses=statuses,
            input_document_id=input_document_id,
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
        finished_at = self._ensure_utc(run.finished_at)
        duration_seconds = (
            (finished_at - started_at).total_seconds() if started_at and finished_at else None
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
            completed_at=finished_at,
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
                "completed_at": _dt_iso(run.finished_at),
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
        selected_sheet_names = self._select_input_sheet_names(options)
        if not selected_sheet_names and run.input_sheet_names:
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
        log_level = getattr(options, "log_level", None) or ("DEBUG" if options.debug else "INFO")
        command.extend(["--log-level", str(log_level)])

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
        summary_json = self._serialize_summary(
            await self._build_placeholder_summary(
                run=run,
                status=RunStatus.SUCCEEDED,
                message="Validation-only execution",
            )
        )
        completion = await self._complete_run(
            run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
            summary=summary_json,
        )
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
        summary_json = self._serialize_summary(
            await self._build_placeholder_summary(
                run=run,
                status=RunStatus.SUCCEEDED,
                message=message,
            )
        )
        completion = await self._complete_run(
            run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
            summary=summary_json,
        )

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

                    summary_json = frame.summary_json
                    if summary_json is None and frame.summary_model is not None:
                        summary_json = self._serialize_summary(frame.summary_model)

                    completion = await self._complete_run(
                        run,
                        status=frame.status,
                        exit_code=frame.return_code,
                        error_message=frame.error_message,
                        summary=summary_json,
                    )
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
            completion = await self._complete_run(
                run,
                status=RunStatus.CANCELLED,
                exit_code=None,
                error_message="Run execution cancelled",
            )
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
            completion = await self._complete_run(
                run,
                status=RunStatus.FAILED,
                exit_code=None,
                error_message=str(exc),
            )
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

    async def _transition_status(self, run: Run, status: RunStatus) -> Run:
        if status is RunStatus.RUNNING:
            run.started_at = run.started_at or utc_now()
        run.status = status
        await self._session.commit()
        await self._session.refresh(run)
        logger.debug(
            "run.status.transition",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                status=run.status.value,
            ),
        )
        return run

    async def _complete_run(
        self,
        run: Run,
        *,
        status: RunStatus,
        exit_code: int | None,
        summary: str | None = None,
        error_message: str | None = None,
    ) -> Run:
        run.status = status
        run.exit_code = exit_code
        if error_message is not None:
            run.error_message = error_message
        if summary is not None:
            run.summary = summary
        run.finished_at = utc_now()
        run.cancelled_at = utc_now() if status is RunStatus.CANCELLED else None
        await self._session.commit()
        await self._session.refresh(run)

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
        return run

    async def _build_placeholder_summary(
        self,
        *,
        run: Run,
        status: RunStatus,
        message: str,
    ) -> dict[str, Any]:
        """Construct a minimal run summary payload without engine output."""

        return {
            "run_id": str(run.id),
            "status": status.value,
            "message": message,
        }

    @staticmethod
    def _serialize_summary(summary: Any) -> str:
        if isinstance(summary, str):
            return summary
        try:
            return json.dumps(summary, default=str)
        except TypeError:
            return json.dumps(str(summary))

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
    def _generate_run_id() -> UUID:
        return generate_uuid7()

    @staticmethod
    def _epoch_seconds(dt: datetime | None) -> int | None:
        if dt is None:
            return None
        return int(dt.timestamp())

    @staticmethod
    def _duration_ms(run: Run) -> int | None:
        if run.started_at and run.finished_at:
            return int((run.finished_at - run.started_at).total_seconds() * 1000)
        return None

    @staticmethod
    def _format_mode_message(options: RunCreateOptions) -> str | None:
        """Render a one-line banner describing special run modes, if any."""

        modes: list[str] = []
        if options.dry_run:
            modes.append("dry-run enabled")
        if options.validate_only:
            modes.append("validate-only mode")
        if not modes:
            return None
        return "Run options: " + ", ".join(modes)

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
                "options": options.model_dump(exclude_none=True),
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
