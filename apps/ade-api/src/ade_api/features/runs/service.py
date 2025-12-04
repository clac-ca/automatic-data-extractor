"""Run orchestration service coordinating DB state and engine execution."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from ade_engine.schemas import (
    AdeEvent,
    AdeEventPayload,
    ColumnCounts,
    ConsoleLinePayload,
    Counts,
    FieldCounts,
    FieldSummaryAggregate,
    ManifestV1,
    RowCounts,
    RunCompletedPayload,
    RunQueuedPayload,
    RunSummary,
    ValidationSummary,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.encoding import json_dumps
from ade_api.common.ids import generate_uuid7
from ade_api.common.logging import log_context
from ade_api.common.pagination import Page
from ade_api.common.time import utc_now
from ade_api.core.models import (
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    Run,
    RunStatus,
)
from ade_api.features.builds.event_dispatcher import BuildEventDispatcher
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.features.builds.service import BuildExecutionContext, BuildsService
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.documents.repository import DocumentsRepository
from ade_api.features.documents.staging import stage_document_input
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.emitters import RunEventEmitter
from ade_api.features.system_settings.schemas import SafeModeStatus
from ade_api.features.system_settings.service import (
    SAFE_MODE_DEFAULT_DETAIL,
    SafeModeService,
)
from ade_api.infra.storage import (
    build_venv_root,
    workspace_config_root,
    workspace_documents_root,
    workspace_run_root,
)
from ade_api.settings import Settings

from .event_dispatcher import RunEventDispatcher, RunEventLogReader, RunEventStorage
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
    "RunOutputMissingError",
    "RunsService",
    "RunStreamFrame",
]

logger = logging.getLogger(__name__)
event_logger = logging.getLogger("ade_api.runs.events")

DEFAULT_EVENTS_PAGE_LIMIT = 1000

# Stream frames are AdeEvents as far as the public API is concerned. Internally
# we also see StdoutFrame objects from the process runner and RunExecutionResult
# markers used to finalize runs.
@dataclass(slots=True)
class RunExecutionResult:
    """Outcome of an engine-backed run execution."""

    status: RunStatus
    return_code: int | None
    summary_model: RunSummary | None
    summary_json: str | None
    paths_snapshot: RunPathsSnapshot
    error_message: str | None = None


RunStreamFrame = AdeEvent | StdoutFrame | RunExecutionResult


# --------------------------------------------------------------------------- #
# Small supporting types
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RunPathsSnapshot:
    """Container for run-relative output and log paths.

    This is the normalized view that higher layers use. All paths here are
    relative to the runs root, so they are safe to surface externally.
    """

    events_path: str | None = None
    output_paths: list[str] = field(default_factory=list)
    processed_files: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class RunExecutionContext:
    """Minimal data required to execute a run outside the request scope."""

    run_id: UUID
    configuration_id: UUID
    workspace_id: UUID
    venv_path: str
    build_id: UUID
    runs_dir: str | None = None
    build_context: BuildExecutionContext | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "configuration_id": str(self.configuration_id),
            "workspace_id": str(self.workspace_id),
            "venv_path": self.venv_path,
            "build_id": str(self.build_id),
            "runs_dir": self.runs_dir or "",
            "build_context": self.build_context.as_dict() if self.build_context else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RunExecutionContext:
        return cls(
            run_id=UUID(str(payload["run_id"])),
            configuration_id=UUID(str(payload["configuration_id"])),
            workspace_id=UUID(str(payload["workspace_id"])),
            venv_path=payload["venv_path"],
            build_id=UUID(str(payload["build_id"])),
            runs_dir=payload.get("runs_dir") or None,
            build_context=(
                BuildExecutionContext.from_dict(payload["build_context"])
                if payload.get("build_context")
                else None
            ),
        )


# --------------------------------------------------------------------------- #
# Error types
# --------------------------------------------------------------------------- #


class RunNotFoundError(RuntimeError):
    """Raised when a requested run row cannot be located."""


class RunDocumentMissingError(RuntimeError):
    """Raised when a requested input document cannot be located."""


class RunLogsFileMissingError(RuntimeError):
    """Raised when a requested run log file cannot be read."""


class RunOutputMissingError(RuntimeError):
    """Raised when requested run outputs cannot be resolved."""


class RunInputMissingError(RuntimeError):
    """Raised when a run is attempted without required staged inputs."""


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
        event_dispatcher: RunEventDispatcher | None = None,
        event_storage: RunEventStorage | None = None,
        build_event_dispatcher: BuildEventDispatcher | None = None,
    ) -> None:
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
        self._builds_service = BuildsService(
            session=session,
            settings=settings,
            storage=self._storage,
            event_dispatcher=build_event_dispatcher,
            event_storage=(build_event_dispatcher.storage if build_event_dispatcher else None),
        )
        if event_dispatcher and event_storage is None:
            event_storage = event_dispatcher.storage
        self._event_storage = event_storage or RunEventStorage(settings=settings)
        self._event_dispatcher = event_dispatcher or RunEventDispatcher(
            storage=self._event_storage
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
    ) -> tuple[Run, RunExecutionContext]:
        """Create the queued run row and return its execution context."""

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

        # Optional primary input document descriptor
        input_document_id = options.input_document_id or None
        document_descriptor: dict[str, Any] | None = None
        if input_document_id:
            document = await self._require_document(
                workspace_id=configuration.workspace_id,
                document_id=input_document_id,
            )
            document_descriptor = self._document_descriptor(document)

        run_id = self._generate_run_id()

        build, build_ctx = await self._builds_service.ensure_build_for_run(
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            force_rebuild=options.force_rebuild,
            run_id=run_id,
            reason="on_demand",
        )
        build_id = build.id
        venv_root = (
            Path(build_ctx.venv_root)
            if build_ctx
            else build_venv_root(
                self._settings,
                configuration.workspace_id,
                configuration.id,
                build_id,
            )
        )
        venv_path = venv_root / ".venv"
        run_status = (
            RunStatus.WAITING_FOR_BUILD
            if build.status is not BuildStatus.READY
            else RunStatus.QUEUED
        )

        selected_sheet_name = self._select_input_sheet_name(options)

        run = Run(
            id=run_id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            status=run_status,
            attempt=1,
            retry_of_run_id=None,
            trace_id=str(run_id),
            input_document_id=input_document_id,
            input_documents=[document_descriptor] if document_descriptor else [],
            input_sheet_name=selected_sheet_name,
            input_sheet_names=(
                options.input_sheet_names
                or ([selected_sheet_name] if selected_sheet_name else None)
            ),
            build_id=build_id,
        )
        self._session.add(run)

        # Touch configuration usage timestamp.
        configuration.last_used_at = utc_now()  # type: ignore[attr-defined]

        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(run)

        runs_root = workspace_run_root(self._settings, configuration.workspace_id)
        context = RunExecutionContext(
            run_id=run.id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            venv_path=str(venv_path),
            build_id=build_id,
            runs_dir=str(runs_root),
            build_context=build_ctx if (build.status is not BuildStatus.READY) else None,
        )

        mode_literal = "validate" if options.validate_only else "execute"
        await self._emit_api_event(
            run=run,
            type_="run.queued",
            payload=RunQueuedPayload(
                status="queued",
                mode=mode_literal,
                options=options.model_dump(),
            ),
        )
        if run.status is RunStatus.WAITING_FOR_BUILD:
            await self._emit_api_event(
                run=run,
                type_="run.waiting_for_build",
                payload={
                    "status": "waiting_for_build",
                    "reason": "build_not_ready",
                    "build_id": str(build_id),
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
        return run, context

    async def run_to_completion(
        self,
        *,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> None:
        """Execute the run, exhausting the event stream."""

        logger.info(
            "run.execute.start",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                run_id=context.run_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )
        async for _ in self.stream_run(context=context, options=options):
            pass
        logger.info(
            "run.execute.completed",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                run_id=context.run_id,
                validate_only=options.validate_only,
                dry_run=options.dry_run,
            ),
        )

    async def stream_run(
        self,
        *,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> AsyncIterator[RunStreamFrame]:
        """Iterate through run events while executing the engine."""

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

        if context.build_context:
            build_context = context.build_context
            build_options = BuildCreateOptions(force=options.force_rebuild, wait=True)
            if build_context.should_run:
                async for event in self._builds_service.stream_build(
                    context=build_context,
                    options=build_options,
                ):
                    forwarded = await self._event_dispatcher.emit(
                        type=event.type,
                        source=event.source or "api",
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                        build_id=event.build_id or build_context.build_id,
                        payload=event.payload,
                    )
                    yield forwarded
            else:
                build = await self._builds_service.get_build_or_raise(
                    build_context.build_id,
                    workspace_id=build_context.workspace_id,
                )
                reader = self._builds_service.event_log_reader(
                    workspace_id=build.workspace_id,
                    configuration_id=build.configuration_id,
                    build_id=build.id,
                )
                last_sequence = 0
                for event in reader.iter(after_sequence=0):
                    forwarded = await self._event_dispatcher.emit(
                        type=event.type,
                        source=event.source or "api",
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                        build_id=event.build_id or build_context.build_id,
                        payload=event.payload,
                    )
                    yield forwarded
                    if event.sequence:
                        last_sequence = max(last_sequence, event.sequence)
                async with self._builds_service.subscribe_to_events(build.id) as subscription:
                    async for live_event in subscription:
                        if live_event.sequence and live_event.sequence <= last_sequence:
                            continue
                        forwarded = await self._event_dispatcher.emit(
                            type=live_event.type,
                            source=live_event.source or "api",
                            workspace_id=run.workspace_id,
                            configuration_id=run.configuration_id,
                            run_id=run.id,
                            build_id=live_event.build_id or build_context.build_id,
                            payload=live_event.payload,
                        )
                        yield forwarded
                        if live_event.sequence:
                            last_sequence = live_event.sequence
                        if live_event.type in {"build.complete", "build.failed"}:
                            break

            build = await self._builds_service.get_build_or_raise(
                build_context.build_id,
                workspace_id=build_context.workspace_id,
            )
            if build.status is not BuildStatus.READY:
                error_message = build.error_message or (
                    f"Configuration {build.configuration_id} build failed"
                )
                yield await self._emit_api_event(
                    run=run,
                    type_="console.line",
                    payload=ConsoleLinePayload(
                        scope="run",
                        stream="stderr",
                        level="error",
                        message=error_message,
                    ),
                )
                run_dir = self._run_dir_for_run(
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                )
                paths_snapshot = self._finalize_paths(
                    summary=None,
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
                        failure_code="build_failed",
                        failure_message=error_message,
                    ),
                )
                return

            venv_path = await self._builds_service.ensure_local_env(build=build)
            build_done_message = "Configuration build completed; starting ADE run."
            yield await self._emit_api_event(
                run=run,
                type_="console.line",
                payload=ConsoleLinePayload(
                    scope="run",
                    stream="stdout",
                    level="info",
                    message=build_done_message,
                ),
            )
            context = RunExecutionContext(
                run_id=context.run_id,
                configuration_id=context.configuration_id,
                workspace_id=context.workspace_id,
                venv_path=str(venv_path),
                build_id=context.build_id,
                runs_dir=context.runs_dir,
                build_context=None,
            )

        run = await self._transition_status(run, RunStatus.RUNNING)
        run_emitter = self._run_event_emitter(run)
        yield await run_emitter.start(mode=mode_literal)
        safe_mode = await self._safe_mode_status()

        # Emit a one-time console banner describing the mode, if applicable.
        mode_message = self._format_mode_message(options)
        if mode_message:
            yield await self._emit_api_event(
                run=run,
                type_="console.line",
                payload=ConsoleLinePayload(
                    scope="run",
                    stream="stdout",
                    level="info",
                    message=mode_message,
                ),
            )

        # Validation-only short circuit: we never touch the engine.
        if options.validate_only:
            logger.debug(
                "run.stream.validate_only_short_circuit",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                ),
            )
            async for event in self._stream_validate_only_run(
                run=run,
                mode_literal=mode_literal,
            ):
                yield event
            return

        # Safe mode short circuit: log, synthesize a summary, and exit.
        if safe_mode.enabled:
            logger.debug(
                "run.stream.safe_mode_short_circuit",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    safe_mode_enabled=True,
                ),
            )
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
            payload=ConsoleLinePayload(
                scope="run",
                stream="stderr",
                level="error",
                message=message,
            ),
        )

        placeholder_summary = await self._build_placeholder_summary(
            run=run,
            status=RunStatus.FAILED,
            message=str(error),
        )
        summary_json = self._serialize_summary(placeholder_summary)
        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
        paths_snapshot = self._finalize_paths(
            summary=placeholder_summary.model_dump(mode="json"),
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )
        completion = await self._complete_run(
            run,
            status=RunStatus.FAILED,
            exit_code=None,
            summary=summary_json,
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
                summary=placeholder_summary.model_dump(mode="json"),
            ),
        )

    async def handle_background_failure(
        self,
        *,
        context: RunExecutionContext,
        options: RunCreateOptions,
        error: Exception,
    ) -> AsyncIterator[AdeEvent]:
        """Surface background task failures via console + completion events."""

        async for event in self._handle_stream_failure(
            context=context,
            options=options,
            error=error,
        ):
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

    async def get_run_summary(self, run_id: UUID) -> RunSummary | None:
        """Return a RunSummary for ``run_id`` if available or derivable."""

        logger.debug(
            "run.summary.get.start",
            extra=log_context(run_id=run_id),
        )
        run = await self._require_run(run_id)
        summary_payload = self._deserialize_run_summary(run.summary)
        if isinstance(summary_payload, dict):
            try:
                summary = RunSummary.model_validate(summary_payload)
                logger.info(
                    "run.summary.get.cached",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                    ),
                )
                return summary
            except ValidationError:
                logger.warning(
                    "run.summary.get.cached_invalid",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                    ),
                )
        return None

    async def get_run_events(
        self,
        *,
        run_id: UUID,
        after_sequence: int | None = None,
        limit: int = DEFAULT_EVENTS_PAGE_LIMIT,
    ) -> tuple[list[AdeEvent], int | None]:
        """Return ADE telemetry events for ``run_id`` with optional paging."""

        logger.debug(
            "run.events.get.start",
            extra=log_context(
                run_id=run_id, after_sequence=after_sequence, limit=limit
            ),
        )
        run = await self._require_run(run_id)
        events: list[AdeEvent] = []
        next_after: int | None = None
        reader = self.event_log_reader(
            workspace_id=run.workspace_id, run_id=run.id
        )
        for event in reader.iter(after_sequence=after_sequence):
            events.append(event)
            if len(events) >= limit:
                next_after = event.sequence
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
        resources = [self.to_resource(run) for run in page_result.items]
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

    def to_resource(self, run: Run) -> RunResource:
        """Convert ``run`` into its API representation."""

        run_dir = self._run_dir_for_run(
            workspace_id=run.workspace_id,
            run_id=run.id,
        )
        summary_payload = self._deserialize_run_summary(run.summary)
        summary_source = (
            summary_payload.get("source")
            if isinstance(summary_payload, dict)
            else {}
        )
        summary_counts = (
            summary_payload.get("counts")
            if isinstance(summary_payload, dict)
            else {}
        )
        summary_details = (
            summary_payload.get("details")
            if isinstance(summary_payload, dict)
            else {}
        )

        summary_for_paths: dict[str, Any] | None = None
        if isinstance(summary_details, dict) and summary_details:
            summary_for_paths = summary_details
        elif isinstance(summary_payload, dict):
            summary_for_paths = summary_payload

        paths = self._finalize_paths(
            summary=summary_for_paths,
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
        )

        # Input documents
        document_ids = [
            str(doc["document_id"])
            for doc in (run.input_documents or [])
            if isinstance(doc, dict) and doc.get("document_id")
        ]
        if run.input_document_id and run.input_document_id not in document_ids:
            document_ids.append(run.input_document_id)

        # Input sheets
        sheet_names = run.input_sheet_names or []
        if run.input_sheet_name and run.input_sheet_name not in sheet_names:
            sheet_names.append(run.input_sheet_name)

        # Outputs and processed files
        output_files = paths.output_paths or self._relative_output_paths(run_dir / "output")
        processed_files = list(paths.processed_files or [])
        if not processed_files and isinstance(summary_details, dict):
            processed_files = [
                str(item) for item in summary_details.get("processed_files", []) or []
            ]

        # Timing and failure info
        started_at = self._ensure_utc(run.started_at) or self._coerce_datetime(
            summary_source.get("started_at")
        )
        finished_at = self._ensure_utc(run.finished_at) or self._coerce_datetime(
            summary_source.get("completed_at")
        )
        duration_seconds = (
            (finished_at - started_at).total_seconds()
            if started_at and finished_at
            else None
        )

        failure_info = summary_source.get("failure", {})
        failure_code = failure_info.get("code")
        failure_stage = failure_info.get("stage")
        failure_message = run.error_message or failure_info.get("message")

        files_counts = summary_counts.get("files") if isinstance(summary_counts, dict) else {}
        sheets_counts = summary_counts.get("sheets") if isinstance(summary_counts, dict) else {}

        # Defensive: ensure we always have dict-like counts so .get calls below are safe
        if not isinstance(files_counts, dict):
            files_counts = {}
        if not isinstance(sheets_counts, dict):
            sheets_counts = {}

        return RunResource(
            id=run.id,
            workspace_id=run.workspace_id,
            configuration_id=run.configuration_id,
            build_id=run.build_id,
            status=run.status,
            failure_code=failure_code,
            failure_stage=failure_stage,
            failure_message=failure_message,
            engine_version=summary_source.get("engine_version"),
            config_version=summary_source.get("config_version"),
            env_reason=summary_source.get("env_reason"),
            env_reused=summary_source.get("env_reused"),
            created_at=self._ensure_utc(run.created_at) or utc_now(),
            started_at=started_at,
            completed_at=finished_at,
            duration_seconds=duration_seconds,
            exit_code=run.exit_code,
            input=RunInput(
                document_ids=document_ids,
                input_sheet_names=sheet_names,
                input_file_count=files_counts.get("total"),
                input_sheet_count=sheets_counts.get("total"),
            ),
            output=RunOutput(
                has_outputs=bool(output_files),
                output_count=len(output_files),
                processed_files=processed_files,
            ),
            links=self._links(run.id),
        )

    @staticmethod
    def _links(run_id: UUID) -> RunLinks:
        base = f"/api/v1/runs/{run_id}"
        return RunLinks(
            self=base,
            summary=f"{base}/summary",
            events=f"{base}/events",
            events_stream=f"{base}/events/stream",
            logs=f"{base}/logs",
            outputs=f"{base}/outputs",
        )

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

    async def list_output_files(self, *, run_id: UUID) -> list[tuple[str, int]]:
        """Return output file tuples for ``run_id``."""

        logger.debug(
            "run.outputs.list.start",
            extra=log_context(run_id=run_id),
        )
        run = await self._require_run(run_id)
        output_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id) / "output"
        if not output_dir.exists() or not output_dir.is_dir():
            logger.warning(
                "run.outputs.list.missing",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(output_dir),
                ),
            )
            raise RunOutputMissingError("Run output is unavailable")

        files: list[tuple[str, int]] = []
        for path in output_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(output_dir)
            except ValueError:
                continue
            files.append((str(relative), path.stat().st_size))

        logger.info(
            "run.outputs.list.success",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                count=len(files),
            ),
        )
        return files

    async def resolve_output_file(
        self,
        *,
        run_id: UUID,
        relative_path: str,
    ) -> Path:
        """Return the absolute path for ``relative_path`` in ``run_id`` outputs."""

        logger.debug(
            "run.outputs.resolve.start",
            extra=log_context(run_id=run_id, path=relative_path),
        )
        run = await self._require_run(run_id)
        output_dir = (
            self._run_dir_for_run(
                workspace_id=run.workspace_id,
                run_id=run.id,
            )
            / "output"
        )
        if not output_dir.exists() or not output_dir.is_dir():
            logger.warning(
                "run.outputs.resolve.missing_root",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    path=str(output_dir),
                ),
            )
            raise RunOutputMissingError("Run output is unavailable")

        candidate = (output_dir / relative_path).resolve()
        try:
            candidate.relative_to(output_dir)
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

    def run_relative_path(self, path: Path) -> str:
        """Return ``path`` relative to the runs root, validating traversal."""

        root = self._runs_dir.resolve()
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

    def _relative_if_exists(self, path: str | Path | None) -> str | None:
        if path is None:
            return None
        candidate = Path(path)
        if not candidate.exists():
            return None
        try:
            return self.run_relative_path(candidate)
        except RunOutputMissingError:
            return None

    def _relative_output_paths(self, output_dir: Path) -> list[str]:
        if not output_dir.exists() or not output_dir.is_dir():
            return []
        paths: list[str] = []
        for path in sorted(p for p in output_dir.rglob("*") if p.is_file()):
            relative = self._relative_if_exists(path)
            if relative is not None:
                paths.append(relative)
        return paths

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
        summary: dict[str, Any] | None,
        run_dir: Path,
        default_paths: RunPathsSnapshot,
    ) -> RunPathsSnapshot:
        """Merge summary-derived paths with inferred filesystem paths."""

        snapshot = RunPathsSnapshot(
            events_path=default_paths.events_path,
            output_paths=list(default_paths.output_paths),
            processed_files=list(default_paths.processed_files),
        )
        details = summary.get("details") if isinstance(summary, dict) else None
        if not isinstance(details, dict):
            details = summary if isinstance(summary, dict) else {}

        # Events path: summary beats defaults, then fall back to logs/events.ndjson.
        logs_dir = run_dir / "logs"
        event_candidates: list[str | Path | None] = [
            logs_dir / "events.ndjson",
            details.get("events_path") if isinstance(details, dict) else None,
        ]
        for candidate in event_candidates:
            snapshot.events_path = self._relative_if_exists(candidate)
            if snapshot.events_path:
                break

        # Output paths: summary-specified relative paths first, then scan output dir.
        output_candidates = details.get("output_paths") if isinstance(details, dict) else None
        if isinstance(output_candidates, list):
            snapshot.output_paths = [
                p
                for p in (self._relative_if_exists(path) for path in output_candidates)
                if p
            ]

        if not snapshot.output_paths:
            snapshot.output_paths = self._relative_output_paths(run_dir / "output")

        # Processed files: summary value if present, otherwise leave as-is.
        processed_candidates = details.get("processed_files") if isinstance(details, dict) else None
        if isinstance(processed_candidates, list):
            snapshot.processed_files = [str(path) for path in processed_candidates]

        return snapshot

    @staticmethod
    def _parse_summary(
        line: str,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Best-effort parse of a JSON summary line from the engine CLI."""

        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            return default
        return candidate if isinstance(candidate, dict) else default

    @staticmethod
    def _deserialize_run_summary(summary: str | None) -> dict[str, Any] | None:
        if summary is None:
            return None
        try:
            candidate = json.loads(summary)
        except json.JSONDecodeError:
            return None
        return candidate if isinstance(candidate, dict) else None

    @staticmethod
    def _serialize_summary(summary: RunSummary | None) -> str | None:
        return summary.model_dump_json() if summary else None

    def _run_completed_payload(
        self,
        *,
        run: Run,
        paths: RunPathsSnapshot,
        failure_stage: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> RunCompletedPayload:
        failure: dict[str, Any] | None = None
        if any([failure_stage, failure_code, failure_message]):
            failure = {
                "stage": failure_stage,
                "code": failure_code,
                "message": failure_message,
            }

        summary_payload = (
            summary
            if isinstance(summary, dict)
            else self._deserialize_run_summary(run.summary)
        )
        if not isinstance(summary_payload, dict):
            summary_payload = {}

        run_block = summary_payload.get("run")
        if not isinstance(run_block, dict):
            run_block = {}

        run_block.setdefault("id", str(run.id))
        run_block.setdefault(
            "status",
            run.status.value if hasattr(run.status, "value") else str(run.status),
        )
        if run.started_at:
            run_block.setdefault("started_at", self._ensure_utc(run.started_at))
        if run.finished_at:
            run_block.setdefault("completed_at", self._ensure_utc(run.finished_at))
        if paths.output_paths:
            run_block.setdefault("outputs", list(paths.output_paths))

        failure_hint = failure_message or run.error_message
        if isinstance(failure, dict):
            failure_hint = failure_hint or failure.get("message")
        if failure_hint:
            run_block.setdefault("failure_message", failure_hint)

        summary_payload["run"] = run_block

        return RunCompletedPayload(
            status=run.status,
            failure=failure,
            execution={
                "exit_code": run.exit_code,
                "started_at": self._ensure_utc(run.started_at),
                "completed_at": self._ensure_utc(run.finished_at),
                "duration_ms": self._duration_ms(run),
            },
            artifacts={
                "output_paths": paths.output_paths,
                "events_path": paths.events_path,
            },
            summary=summary_payload or {},
        )

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
        summary: dict[str, Any] | None,
        return_code: int,
    ) -> tuple[RunStatus, str | None]:
        """Resolve final RunStatus and error message from exit code + summary."""

        status = RunStatus.SUCCEEDED if return_code == 0 else RunStatus.FAILED
        error_message: str | None = (
            None if status is RunStatus.SUCCEEDED else f"Process exited with {return_code}"
        )

        if summary:
            summary_status = summary.get("status")
            if summary_status == "failed":
                status = RunStatus.FAILED
                error = summary.get("error")
                if isinstance(error, dict):
                    error_message = error.get("message", error_message)
            elif summary_status == "succeeded":
                status = RunStatus.SUCCEEDED
                error_message = None
            elif summary_status == "cancelled":
                status = RunStatus.CANCELLED
                error = summary.get("error")
                error_message = (
                    error.get("message") if isinstance(error, dict) else None
                ) or "Run cancelled"

        return status, error_message

    def _manifest_path(self, workspace_id: UUID, configuration_id: UUID) -> Path:
        return (
            workspace_config_root(
                self._settings,
                workspace_id,
                configuration_id,
            )
            / "src"
            / "ade_config"
            / "manifest.json"
        )

    def _load_manifest(self, workspace_id: UUID, configuration_id: UUID) -> ManifestV1 | None:
        path = self._manifest_path(workspace_id, configuration_id)
        if not path.exists():
            return None
        try:
            return ManifestV1.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, OSError, ValueError):
            logger.warning(
                "run.manifest.parse_failed",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    path=str(path),
                ),
            )
            return None

    async def _persist_run_summary(self, *, run: Run, summary_json: str | None) -> None:
        if summary_json is None:
            return

        run.summary = summary_json
        await self._session.commit()
        await self._session.refresh(run)
        logger.info(
            "run.summary.persisted",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
            ),
        )

    async def _build_placeholder_summary(
        self,
        *,
        run: Run,
        status: RunStatus,
        message: str | None = None,
        failure_code: str | None = None,
        failure_stage: str | None = None,
    ) -> RunSummary:
        """Synthesize a minimal RunSummary when engine execution is skipped."""

        manifest = await asyncio.to_thread(
            self._load_manifest,
            run.workspace_id,
            run.configuration_id,
        )
        started = self._ensure_utc(run.started_at) or utc_now()
        completed = self._ensure_utc(run.finished_at) or utc_now()
        status_literal = status.value
        field_total = len(manifest.columns.fields) if manifest else 0  # type: ignore[union-attr]
        required_total = (
            len([f for f in manifest.columns.fields.values() if f.required]) if manifest else 0  # type: ignore[union-attr]
        )

        field_summaries: list[FieldSummaryAggregate] = []
        if manifest:
            for field_name in manifest.columns.order:
                field_cfg = manifest.columns.fields.get(field_name)
                if field_cfg is None:
                    continue
                field_summaries.append(
                    FieldSummaryAggregate(
                        field=field_name,
                        label=field_cfg.label,
                        required=bool(field_cfg.required),
                        mapped=False,
                        max_score=None,
                        tables_mapped=0,
                        sheets_mapped=0,
                        files_mapped=0,
                    )
                )

        failure = {
            "code": failure_code or ("cancelled" if status is RunStatus.CANCELLED else None),
            "stage": failure_stage,
            "message": message,
        }
        failure = {k: v for k, v in failure.items() if v is not None}

        counts = Counts(
            files={"total": 0},
            sheets={"total": 0},
            tables={"total": 0},
            rows=RowCounts(total=0, empty=0, non_empty=0),
            columns=ColumnCounts(
                physical_total=0,
                physical_empty=0,
                physical_non_empty=0,
                distinct_headers=0,
                distinct_headers_mapped=0,
                distinct_headers_unmapped=0,
            ),
            fields=FieldCounts(
                total=field_total,
                required=required_total,
                mapped=0,
                unmapped=field_total,
                required_mapped=0,
                required_unmapped=required_total,
            ),
        )

        details: dict[str, Any] = {}
        if message:
            details["message"] = message

        return RunSummary(
            scope="run",
            id="run",
            parent_ids={"run_id": str(run.id)},
            source={
                "run_id": str(run.id),
                "workspace_id": str(run.workspace_id),
                "configuration_id": str(run.configuration_id),
                "build_id": str(run.build_id) if run.build_id else None,
                "engine_version": getattr(run, "engine_version", None),
                "config_version": manifest.version if manifest else None,  # type: ignore[union-attr]
                "started_at": started,
                "completed_at": completed,
                "status": status_literal,
                "failure": failure,
            },
            counts=counts,
            fields=field_summaries,
            columns=[],
            validation=ValidationSummary(),
            details=details,
        )

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
        """Invoke the engine process and stream ADE events back to the caller."""

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

        python = self._resolve_python(Path(context.venv_path))
        env = self._build_env(Path(context.venv_path), options, context)
        runs_root = (
            Path(context.runs_dir)
            if context.runs_dir
            else workspace_run_root(self._settings, context.workspace_id)
        )
        run_dir = runs_root / str(run.id)
        run_dir.mkdir(parents=True, exist_ok=True)

        if not options.input_document_id:
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
            document_id=options.input_document_id,
            run_dir=run_dir,
        )

        engine_logs_dir = run_dir / "engine-logs"
        engine_logs_dir.mkdir(parents=True, exist_ok=True)

        command = [str(python), "-m", "ade_engine", "run"]
        command.extend(["--input", str(staged_input)])
        command.extend(["--output-dir", str(run_dir / "output")])
        command.extend(["--logs-dir", str(engine_logs_dir)])

        sheets = options.input_sheet_names or []
        if options.input_sheet_name:
            sheets.append(options.input_sheet_name)
        for sheet in sheets:
            command.extend(["--input-sheet", sheet])

        metadata: dict[str, str] = {
            "run_id": run.id,
            "configuration_id": run.configuration_id,
            "workspace_id": run.workspace_id,
            "context_configuration_id": context.configuration_id,
        }
        if options.metadata:
            for key, value in options.metadata.items():
                metadata[key] = str(value)
        for key, value in metadata.items():
            command.extend(["--metadata", f"{key}={value}"])

        if safe_mode_enabled:
            command.append("--safe-mode")

        runner = EngineSubprocessRunner(
            command=command,
            logs_dir=engine_logs_dir,
            env=env,
        )

        paths_snapshot = RunPathsSnapshot()

        # Stream frames from the engine process: either StdoutFrame or AdeEvent.
        async for frame in runner.stream():
            if isinstance(frame, StdoutFrame):
                continue

            # Engine AdeEvents flow through unchanged, mirrored to logs in debug mode.
            self._log_event_debug(frame, origin="engine")
            yield frame

        # Process completion and summarize.
        return_code = runner.returncode if runner.returncode is not None else 1
        status, error_message = self._resolve_completion(None, return_code)

        paths_snapshot = self._finalize_paths(
            summary=None,
            run_dir=run_dir,
            default_paths=paths_snapshot,
        )
        summary_model = None
        summary_json = None

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
            summary_model=summary_model,
            summary_json=summary_json,
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
        placeholder_summary = await self._build_placeholder_summary(
            run=run,
            status=RunStatus.SUCCEEDED,
            message="Validation-only execution",
        )
        summary_json = self._serialize_summary(placeholder_summary)
        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
        paths_snapshot = self._finalize_paths(
            summary=placeholder_summary.model_dump(mode="json"),
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
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
                summary=placeholder_summary.model_dump(mode="json"),
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
        placeholder_summary = await self._build_placeholder_summary(
            run=run,
            status=RunStatus.SUCCEEDED,
            message="Safe mode skip",
        )
        summary_json = self._serialize_summary(placeholder_summary)
        run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
        paths_snapshot = self._finalize_paths(
            summary=placeholder_summary.model_dump(mode="json"),
            run_dir=run_dir,
            default_paths=RunPathsSnapshot(),
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
            payload=ConsoleLinePayload(
                scope="run",
                stream="stdout",
                level="info",
                message=message,
            ),
        )

        # Completion event
        yield await self._emit_api_event(
            run=completion,
            type_="run.complete",
            payload=self._run_completed_payload(
                run=completion,
                paths=paths_snapshot,
                summary=placeholder_summary.model_dump(mode="json"),
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
        """Wrap `_execute_engine` with supervision and error handling."""

        async def generator() -> AsyncIterator[RunStreamFrame]:
            execute_engine = self._execute_engine
            parameters = inspect.signature(execute_engine).parameters
            kwargs: dict[str, object] = {
                "run": run,
                "context": context,
                "options": options,
            }
            if "safe_mode_enabled" in parameters:
                kwargs["safe_mode_enabled"] = safe_mode_enabled

            async for frame in execute_engine(**kwargs):  # type: ignore[misc]
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

        engine_summary: RunSummary | None = None
        engine_summary_json: str | None = None
        latest_paths_snapshot = RunPathsSnapshot()

        try:
            async for event in self._supervisor.stream(
                run.id,
                generator=generator,
            ):
                if isinstance(event, RunExecutionResult):
                    summary_model = engine_summary or event.summary_model
                    summary_json = engine_summary_json or event.summary_json
                    if summary_model and not summary_json:
                        summary_json = self._serialize_summary(summary_model)
                    if summary_model is None:
                        summary_model = await self._build_placeholder_summary(
                            run=run,
                            status=event.status,
                            message=event.error_message or "Engine summary missing",
                            failure_code="engine_summary_missing",
                            failure_stage="engine",
                        )
                        summary_json = self._serialize_summary(summary_model)

                    paths_snapshot = event.paths_snapshot or RunPathsSnapshot()
                    if latest_paths_snapshot.processed_files and not paths_snapshot.processed_files:
                        paths_snapshot.processed_files = list(latest_paths_snapshot.processed_files)
                    if latest_paths_snapshot.output_paths and not paths_snapshot.output_paths:
                        paths_snapshot.output_paths = list(latest_paths_snapshot.output_paths)

                    completion = await self._complete_run(
                        run,
                        status=event.status,
                        exit_code=event.return_code,
                        summary=summary_json,
                        error_message=event.error_message,
                    )
                    yield await self._emit_api_event(
                        run=completion,
                        type_="run.complete",
                        payload=self._run_completed_payload(
                        run=completion,
                        paths=paths_snapshot,
                        failure_stage=(
                            "run"
                            if event.status is RunStatus.FAILED
                            else None
                        ),
                        failure_code=(
                            "engine_summary_missing"
                            if engine_summary is None
                            else None
                        ),
                        failure_message=event.error_message,
                        summary=summary_model.model_dump(mode="json")
                        if summary_model
                        else None,
                    ),
                )
                continue
                if isinstance(event, AdeEvent):
                    payload_dict = event.payload_dict()
                    if event.type == "engine.run.summary":
                        summary_payload = payload_dict
                        try:
                            engine_summary = RunSummary.model_validate(summary_payload)
                            engine_summary_json = self._serialize_summary(engine_summary)
                            await self._persist_run_summary(
                                run=run,
                                summary_json=engine_summary_json,
                            )
                            details = engine_summary.details or {}
                            if (
                                not latest_paths_snapshot.processed_files
                                and isinstance(details, dict)
                            ):
                                processed = details.get("processed_files")
                                if processed:
                                    latest_paths_snapshot.processed_files = [
                                        str(path)
                                        for path in processed
                                    ]
                            if not latest_paths_snapshot.output_paths and isinstance(details, dict):
                                outputs = details.get("output_paths")
                                if outputs:
                                    latest_paths_snapshot.output_paths = [
                                        str(path)
                                        for path in outputs
                                    ]
                        except ValidationError:
                            engine_summary = None
                    elif event.type == "engine.complete" and isinstance(payload_dict, dict):
                        processed_files = payload_dict.get("processed_files")
                        if processed_files:
                            latest_paths_snapshot.processed_files = [
                                str(path)
                                for path in processed_files
                            ]
                        output_paths = payload_dict.get("output_paths")
                        if output_paths:
                            latest_paths_snapshot.output_paths = [
                                str(path)
                                for path in output_paths
                            ]

                forwarded = await self._event_dispatcher.emit(
                    type=event.type,
                    source=event.source or "engine",
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    build_id=getattr(event, "build_id", None) or getattr(run, "build_id", None),
                    payload=getattr(event, "payload", None),
                )
                yield forwarded
        except asyncio.CancelledError:
            logger.warning(
                "run.engine.stream.cancelled",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                ),
            )
            placeholder_summary = await self._build_placeholder_summary(
                run=run,
                status=RunStatus.CANCELLED,
                message="Run execution cancelled",
            )
            summary_json = self._serialize_summary(placeholder_summary)
            run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
            paths_snapshot = self._finalize_paths(
                summary=placeholder_summary.model_dump(mode="json"),
                run_dir=run_dir,
                default_paths=RunPathsSnapshot(),
            )
            completion = await self._complete_run(
                run,
                status=RunStatus.CANCELLED,
                exit_code=None,
                summary=summary_json,
                error_message="Run execution cancelled",
            )
            yield await self._emit_api_event(
                run=completion,
                type_="run.complete",
                payload=self._run_completed_payload(
                    run=completion,
                    paths=paths_snapshot,
                    failure_stage="run",
                    failure_code="run_cancelled",
                    failure_message=completion.error_message,
                    summary=placeholder_summary.model_dump(mode="json"),
                ),
            )
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
            placeholder_summary = await self._build_placeholder_summary(
                run=run,
                status=RunStatus.FAILED,
                message=str(exc),
            )
            summary_json = self._serialize_summary(placeholder_summary)
            run_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id)
            paths_snapshot = self._finalize_paths(
                summary=placeholder_summary.model_dump(mode="json"),
                run_dir=run_dir,
                default_paths=RunPathsSnapshot(),
            )
            completion = await self._complete_run(
                run,
                status=RunStatus.FAILED,
                exit_code=None,
                summary=summary_json,
                error_message=str(exc),
            )
            # Error console frame
            yield await self._emit_api_event(
                run=run,
                type_="console.line",
                payload=ConsoleLinePayload(
                    scope="run",
                    stream="stderr",
                    level="error",
                    message=f"ADE run failed: {exc}",
                ),
            )
            # Run completion frame
            yield await self._emit_api_event(
                run=completion,
                type_="run.complete",
                payload=self._run_completed_payload(
                    run=completion,
                    paths=paths_snapshot,
                    failure_stage="run",
                    failure_code="engine_error",
                    failure_message=completion.error_message,
                    summary=placeholder_summary.model_dump(mode="json"),
                ),
            )
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
        if configuration.status == ConfigurationStatus.INACTIVE:
            logger.warning(
                "run.config.resolve.inactive",
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
        if summary is not None:
            run.summary = summary
        if error_message is not None:
            run.error_message = error_message
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

    @staticmethod
    def _resolve_python(venv_path: Path) -> Path:
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        candidate = venv_path / bin_dir / ("python.exe" if os.name == "nt" else "python")
        if not candidate.exists():
            raise FileNotFoundError(f"Python interpreter not found in {venv_path}")
        return candidate

    @staticmethod
    def _build_env(
        venv_path: Path,
        options: RunCreateOptions,
        context: RunExecutionContext,
    ) -> dict[str, str]:
        env = os.environ.copy()
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        bin_path = venv_path / bin_dir
        env["VIRTUAL_ENV"] = str(venv_path)
        env["PATH"] = os.pathsep.join([str(bin_path), env.get("PATH", "")])
        if options.dry_run:
            env["ADE_RUN_DRY_RUN"] = "1"
        if options.validate_only:
            env["ADE_RUN_VALIDATE_ONLY"] = "1"
        if options.input_sheet_name:
            env["ADE_RUN_INPUT_SHEET"] = options.input_sheet_name
        if options.input_sheet_names:
            env["ADE_RUN_INPUT_SHEETS"] = json_dumps(options.input_sheet_names)
            if len(options.input_sheet_names) == 1 and not options.input_sheet_name:
                env["ADE_RUN_INPUT_SHEET"] = options.input_sheet_names[0]
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
    def _select_input_sheet_name(options: RunCreateOptions) -> str | None:
        """Resolve a single selected sheet name from the run options, if any."""

        selected = options.input_sheet_name
        if not selected and options.input_sheet_names:
            if len(options.input_sheet_names) == 1:
                selected = options.input_sheet_names[0]
        return selected

    # ------------------------------------------------------------------ #
    # Internal helpers: event logging
    # ------------------------------------------------------------------ #

    @staticmethod
    def _log_event_debug(event: AdeEvent, *, origin: str) -> None:
        """Emit ADE events to the console when debug logging is enabled."""

        if not event_logger.isEnabledFor(logging.DEBUG):
            return

        event_logger.debug(
            "[%s] %s %s",
            origin,
            event.type,
            event.model_dump_json(),
        )

    def _run_event_emitter(self, run: Run) -> RunEventEmitter:
        return RunEventEmitter(
            self._event_dispatcher,
            workspace_id=run.workspace_id,
            configuration_id=run.configuration_id,
            run_id=run.id,
            build_id=getattr(run, "build_id", None),
            source="api",
        )

    async def _emit_api_event(
        self,
        *,
        run: Run,
        type_: str,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        build_id: UUID | None = None,
    ) -> AdeEvent:
        """Emit an AdeEvent originating from the API orchestrator."""

        emitter = self._run_event_emitter(run)
        build_identifier = build_id or getattr(run, "build_id", None)
        event = await emitter.emit(
            type=type_,
            payload=payload,
            extra_ids={"build_id": build_identifier},
        )
        self._log_event_debug(event, origin="api")
        return event

    async def _ensure_run_queued_event(
        self,
        *,
        run: Run,
        mode_literal: str,
        options: RunCreateOptions,
    ) -> AdeEvent | None:
        """Guarantee a single run.queued event exists for the run."""

        last_sequence = self._event_storage.last_sequence(
            workspace_id=run.workspace_id,
            run_id=run.id,
        )
        if last_sequence > 0:
            reader = self.event_log_reader(
                workspace_id=run.workspace_id,
                run_id=run.id,
            )
            return next(iter(reader.iter(after_sequence=0)), None)
        return await self._emit_api_event(
            run=run,
            type_="run.queued",
            payload=RunQueuedPayload(
                status="queued",
                mode=mode_literal,
                options=options.model_dump(),
            ),
        )

    def event_log_reader(self, *, workspace_id: UUID, run_id: UUID) -> RunEventLogReader:
        """Return a reader for persisted run events."""

        return RunEventLogReader(
            storage=self._event_storage,
            workspace_id=workspace_id,
            run_id=run_id,
        )

    def subscribe_to_events(self, run_id: UUID):
        """Expose dispatcher subscription for live event streaming."""

        return self._event_dispatcher.subscribe(run_id)

    @property
    def settings(self) -> Settings:
        """Expose the bound settings instance for caller reuse."""

        return self._settings
