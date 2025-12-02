"""Run orchestration service coordinating DB state and engine execution."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ade_engine.schemas import (
    AdeEvent,
    AdeEventPayload,
    ConsoleLinePayload,
    ManifestV1,
    RunCompletedPayload,
    RunQueuedPayload,
    RunStartedPayload,
    RunSummaryV1,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.logging import log_context
from ade_api.common.pagination import Page
from ade_api.common.encoding import json_dumps
from ade_api.common.time import utc_now
from ade_api.core.models import (
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    Run,
    RunStatus,
)
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.features.builds.service import BuildExecutionContext, BuildsService
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.documents.repository import DocumentsRepository
from ade_api.features.documents.staging import stage_document_input
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.system_settings.schemas import SafeModeStatus
from ade_api.features.system_settings.service import (
    SAFE_MODE_DEFAULT_DETAIL,
    SafeModeService,
)
from ade_api.infra.storage import (
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
from .summary_builder import build_run_summary_from_paths
from .supervisor import RunExecutionSupervisor

__all__ = [
    "RunExecutionContext",
    "RunInputMissingError",
    "RunDocumentMissingError",
    "RunEnvironmentNotReadyError",
    "RunLogsFileMissingError",
    "RunNotFoundError",
    "RunOutputMissingError",
    "RunsService",
    "RunStreamFrame",
]

logger = logging.getLogger(__name__)
event_logger = logging.getLogger("ade_api.runs.events")

DEFAULT_STREAM_LIMIT = 1000

# Stream frames are AdeEvents as far as the public API is concerned. Internally
# we also see StdoutFrame objects from the process runner and RunExecutionResult
# markers used to finalize runs.
@dataclass(slots=True)
class RunExecutionResult:
    """Outcome of an engine-backed run execution."""

    status: RunStatus
    return_code: int | None
    summary_model: RunSummaryV1
    summary_json: str
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

    run_id: str
    configuration_id: str
    workspace_id: str
    venv_path: str
    build_id: str
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
            run_id=payload["run_id"],
            configuration_id=payload["configuration_id"],
            workspace_id=payload["workspace_id"],
            venv_path=payload["venv_path"],
            build_id=payload["build_id"],
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


class RunEnvironmentNotReadyError(RuntimeError):
    """Raised when a configuration lacks an active build to execute."""


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
        configuration_id: str,
        options: RunCreateOptions,
        stream_build: bool = False,
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

        build_ctx: BuildExecutionContext | None = None
        if stream_build:
            build_options = BuildCreateOptions(force=options.force_rebuild, wait=True)
            build, build_ctx = await self._builds_service.prepare_build(
                workspace_id=configuration.workspace_id,
                configuration_id=configuration.id,
                options=build_options,
            )
            build_id = build.id
            venv_path = Path(build_ctx.venv_root) / ".venv"
        else:
            venv_path, build_id = await self._ensure_config_env_ready(
                configuration,
                force_rebuild=options.force_rebuild,
            )

        selected_sheet_name = self._select_input_sheet_name(options)

        run_id = self._generate_run_id()
        run = Run(
            id=run_id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            status=RunStatus.QUEUED,
            attempt=1,
            retry_of_run_id=None,
            trace_id=run_id,
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
            run_id=str(run.id),
            workspace_id=str(configuration.workspace_id),
            configuration_id=str(configuration.id),
            venv_path=str(venv_path),
            build_id=str(build_id),
            runs_dir=str(runs_root),
            build_context=build_ctx,
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

        run = await self._require_run(context.run_id)
        mode_literal = "validate" if options.validate_only else "execute"

        yield await self._emit_api_event(
            run=run,
            type_="run.queued",
            payload=RunQueuedPayload(
                status="queued",
                mode=mode_literal,
                options=options.model_dump(),
            ),
        )

        if context.build_context:
            build_context = context.build_context
            build_options = BuildCreateOptions(force=options.force_rebuild, wait=True)
            async for event in self._builds_service.stream_build(
                context=build_context,
                options=build_options,
            ):
                forwarded = await self._event_dispatcher.emit(
                    type=event.type,
                    source=event.source or "api",
                    workspace_id=str(run.workspace_id),
                    configuration_id=str(run.configuration_id),
                    run_id=str(run.id),
                    build_id=str(event.build_id or build_context.build_id),
                    payload=event.payload,
                )
                yield forwarded
            build = await self._builds_service.get_build_or_raise(
                build_context.build_id,
                workspace_id=build_context.workspace_id,
            )
            if build.status is not BuildStatus.ACTIVE:
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
                    type_="run.completed",
                    payload=self._run_completed_payload(
                        run=completion,
                        summary=None,
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
        safe_mode = await self._safe_mode_status()
        if options.validate_only or safe_mode.enabled:
            yield await self._emit_api_event(
                run=run,
                type_="run.started",
                payload=RunStartedPayload(status="in_progress", mode=mode_literal),
            )

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

    # --------------------------------------------------------------------- #
    # Public read APIs (runs, summaries, events, outputs)
    # --------------------------------------------------------------------- #

    async def get_run(self, run_id: str) -> Run | None:
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

    async def get_run_summary(self, run_id: str) -> RunSummaryV1 | None:
        """Return a RunSummaryV1 for ``run_id`` if available or derivable."""

        logger.debug(
            "run.summary.get.start",
            extra=log_context(run_id=run_id),
        )
        run = await self._require_run(run_id)
        summary_payload = self._deserialize_run_summary(run.summary)
        if isinstance(summary_payload, dict):
            try:
                summary = RunSummaryV1.model_validate(summary_payload)
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
                # Fallback to recomputing from events and manifest below.
                logger.warning(
                    "run.summary.get.cached_invalid",
                    extra=log_context(
                        workspace_id=run.workspace_id,
                        configuration_id=run.configuration_id,
                        run_id=run.id,
                    ),
                )

        paths = self._finalize_paths(
            summary=None,
            run_dir=self._run_dir_for_run(
                workspace_id=run.workspace_id,
                run_id=run.id,
            ),
            default_paths=RunPathsSnapshot(),
        )
        summary = await self._build_run_summary_for_completion(run=run, paths=paths)
        logger.info(
            "run.summary.get.recomputed",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                has_summary=bool(summary),
            ),
        )
        return summary

    async def get_run_events(
        self,
        *,
        run_id: str,
        after_sequence: int | None = None,
        limit: int = DEFAULT_STREAM_LIMIT,
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
        workspace_id: str,
        statuses: Sequence[RunStatus] | None,
        input_document_id: str | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[RunResource]:
        """Return paginated runs for ``workspace_id`` with optional filters."""

        logger.debug(
            "run.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                statuses=[s.value for s in statuses] if statuses else None,
                input_document_id=input_document_id,
                page=page,
                page_size=page_size,
                include_total=include_total,
            ),
        )

        page_result = await self._runs.list_by_workspace(
            workspace_id=workspace_id,
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
                page=response.page,
                page_size=response.page_size,
                count=len(response.items),
                total=response.total,
            ),
        )
        return response

    def to_resource(self, run: Run) -> RunResource:
        """Convert ``run`` into its API representation."""

        run_dir = self._run_dir_for_run(
            workspace_id=run.workspace_id,
            run_id=run.id,
        )
        summary_payload = self._deserialize_run_summary(run.summary)
        summary_run = summary_payload.get("run") if isinstance(summary_payload, dict) else {}
        summary_core = summary_payload.get("core") if isinstance(summary_payload, dict) else {}
        summary_run_dict = summary_run if isinstance(summary_run, dict) else {}
        summary_core_dict = summary_core if isinstance(summary_core, dict) else {}

        paths = self._finalize_paths(
            summary=summary_payload if isinstance(summary_payload, dict) else None,
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
        if not processed_files and isinstance(summary_payload, dict):
            processed_files = [
                str(item) for item in summary_payload.get("processed_files", []) or []
            ]

        # Timing and failure info
        started_at = self._ensure_utc(run.started_at)
        finished_at = self._ensure_utc(run.finished_at)
        duration_seconds = (
            (finished_at - started_at).total_seconds()
            if started_at and finished_at
            else summary_run_dict.get("duration_seconds")
        )

        failure_message = summary_run_dict.get("failure_message")
        if run.error_message:
            failure_message = run.error_message

        return RunResource(
            id=run.id,
            workspace_id=run.workspace_id,
            configuration_id=run.configuration_id,
            build_id=run.build_id,
            status=run.status,
            failure_code=summary_run_dict.get("failure_code"),
            failure_stage=summary_run_dict.get("failure_stage"),
            failure_message=failure_message,
            engine_version=summary_run_dict.get("engine_version"),
            config_version=summary_run_dict.get("config_version"),
            env_reason=summary_run_dict.get("env_reason"),
            env_reused=summary_run_dict.get("env_reused"),
            created_at=self._ensure_utc(run.created_at) or utc_now(),
            started_at=started_at,
            completed_at=finished_at,
            duration_seconds=duration_seconds,
            exit_code=run.exit_code,
            input=RunInput(
                document_ids=document_ids,
                input_sheet_names=sheet_names,
                input_file_count=summary_core_dict.get("input_file_count"),
                input_sheet_count=summary_core_dict.get("input_sheet_count"),
            ),
            output=RunOutput(
                has_outputs=bool(output_files),
                output_count=len(output_files),
                processed_files=processed_files,
            ),
            links=self._links(run.id),
        )

    @staticmethod
    def _links(run_id: str) -> RunLinks:
        base = f"/api/v1/runs/{run_id}"
        return RunLinks(
            self=base,
            summary=f"{base}/summary",
            events=f"{base}/events",
            logs=f"{base}/logs",
            outputs=f"{base}/outputs",
        )

    async def get_logs_file_path(self, *, run_id: str) -> Path:
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

    async def list_output_files(self, *, run_id: str) -> list[tuple[str, int]]:
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
        run_id: str,
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

    def run_directory(self, *, workspace_id: str, run_id: str) -> Path:
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

        # Events path: summary beats defaults, then fall back to logs/events.ndjson.
        logs_dir = run_dir / "logs"
        event_candidates: list[str | Path | None] = [
            logs_dir / "events.ndjson",
            summary.get("events_path") if summary else None,
        ]
        for candidate in event_candidates:
            snapshot.events_path = self._relative_if_exists(candidate)
            if snapshot.events_path:
                break

        # Output paths: summary-specified relative paths first, then scan output dir.
        output_candidates = summary.get("output_paths") if summary else None
        if isinstance(output_candidates, list):
            snapshot.output_paths = [
                p
                for p in (self._relative_if_exists(path) for path in output_candidates)
                if p
            ]

        if not snapshot.output_paths:
            snapshot.output_paths = self._relative_output_paths(run_dir / "output")

        # Processed files: summary value if present, otherwise leave as-is.
        processed_candidates = summary.get("processed_files") if summary else None
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
    def _serialize_summary(summary: RunSummaryV1 | None) -> str | None:
        return summary.model_dump_json() if summary else None

    def _run_completed_payload(
        self,
        *,
        run: Run,
        summary: RunSummaryV1 | None,
        paths: RunPathsSnapshot,
        failure_stage: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> RunCompletedPayload:
        failure: dict[str, Any] | None = None
        if any([failure_stage, failure_code, failure_message]):
            failure = {
                "stage": failure_stage,
                "code": failure_code,
                "message": failure_message,
            }

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
            summary=summary.model_dump(mode="json") if summary else None,
        )

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

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

        return status, error_message

    def _manifest_path(self, workspace_id: str, configuration_id: str) -> Path:
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

    def _load_manifest(self, workspace_id: str, configuration_id: str) -> ManifestV1 | None:
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

    async def _build_run_summary_for_completion(
        self,
        *,
        run: Run,
        paths: RunPathsSnapshot,
    ) -> RunSummaryV1 | None:
        """Build a RunSummaryV1 from the events and manifest when possible."""

        events_path: Path | None
        if paths.events_path:
            events_path = (self._runs_dir / paths.events_path).resolve()
        else:
            events_path = (
                self._run_dir_for_run(
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                )
                / "logs"
                / "events.ndjson"
            )

        if events_path is None or not events_path.exists():
            logger.info(
                "run.summary.build.events_missing",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    events_path=str(events_path),
                ),
            )
            return None

        manifest_path = self._manifest_path(run.workspace_id, run.configuration_id)

        logger.debug(
            "run.summary.build.start",
            extra=log_context(
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
                events_path=str(events_path),
                manifest_path=str(manifest_path),
            ),
        )

        try:
            summary = await asyncio.to_thread(
                build_run_summary_from_paths,
                events_path=events_path if events_path.exists() else None,
                manifest_path=manifest_path if manifest_path.exists() else None,
                workspace_id=run.workspace_id,
                configuration_id=run.configuration_id,
                run_id=run.id,
            )
            logger.info(
                "run.summary.build.success",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                ),
            )
            return summary
        except Exception:
            logger.warning(
                "run.summary.build.failed",
                extra=log_context(
                    workspace_id=run.workspace_id,
                    configuration_id=run.configuration_id,
                    run_id=run.id,
                    events_path=str(events_path),
                ),
                exc_info=True,
            )
            return None

    async def _build_placeholder_summary(
        self,
        *,
        run: Run,
        status: RunStatus,
        message: str | None = None,
    ) -> RunSummaryV1:
        """Synthesize a minimal RunSummaryV1 when engine execution is skipped."""

        manifest = await asyncio.to_thread(
            self._load_manifest,
            run.workspace_id,
            run.configuration_id,
        )
        started = self._ensure_utc(run.started_at) or utc_now()
        completed = self._ensure_utc(run.finished_at) or utc_now()
        status_literal = status.value
        by_field: list[dict[str, Any]] = []
        if manifest:
            for field_name in manifest.columns.order:
                field_cfg = manifest.columns.fields.get(field_name)
                if field_cfg is None:
                    continue
                by_field.append(
                    {
                        "field": field_name,
                        "label": field_cfg.label,
                        "required": field_cfg.required,
                        "mapped": False,
                        "max_score": None,
                        "validation_issue_count_total": 0,
                        "issue_counts_by_severity": {},
                        "issue_counts_by_code": {},
                    }
                )

        return RunSummaryV1(
            run={
                "id": str(run.id),
                "workspace_id": str(run.workspace_id),
                "configuration_id": str(run.configuration_id),
                "status": status_literal,
                "failure_code": "canceled" if status is RunStatus.CANCELED else None,
                "failure_stage": None,
                "failure_message": message,
                "engine_version": getattr(run, "engine_version", None),
                "config_version": manifest.version if manifest else None,  # type: ignore[union-attr]
                "env_reason": None,
                "env_reused": None,
                "started_at": started,
                "completed_at": completed,
                "duration_seconds": (completed - started).total_seconds() if completed else None,
            },
            core={
                "input_file_count": 0,
                "input_sheet_count": 0,
                "table_count": 0,
                "row_count": 0,
                "canonical_field_count": len(manifest.columns.fields) if manifest else 0,  # type: ignore[union-attr]
                "required_field_count": (
                    len([f for f in manifest.columns.fields.values() if f.required])
                    if manifest
                    else 0  # type: ignore[union-attr]
                ),
                "mapped_field_count": 0,
                "unmapped_column_count": 0,
                "validation_issue_count_total": 0,
                "issue_counts_by_severity": {},
                "issue_counts_by_code": {},
            },
            breakdowns={
                "by_file": [],
                "by_field": by_field,
            },
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

        summary: dict[str, Any] | None = None
        paths_snapshot = RunPathsSnapshot()

        # Stream frames from the engine process: either StdoutFrame or AdeEvent.
        async for frame in runner.stream():
            if isinstance(frame, StdoutFrame):
                summary = self._parse_summary(frame.message, default=summary)
                continue

            # Engine AdeEvents flow through unchanged, mirrored to logs in debug mode.
            self._log_event_debug(frame, origin="engine")
            yield frame

        # Process completion and summarize.
        return_code = runner.returncode if runner.returncode is not None else 1
        status, error_message = self._resolve_completion(summary, return_code)

        paths_snapshot = self._finalize_paths(
            summary=summary,
            run_dir=run_dir,
            default_paths=paths_snapshot,
        )
        if summary and summary.get("processed_files"):
            paths_snapshot.processed_files = list(summary.get("processed_files", []))

        summary_model = await self._build_run_summary_for_completion(
            run=run,
            paths=paths_snapshot,
        )
        summary_json = self._serialize_summary(summary_model)

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
            type_="run.completed",
            payload=self._run_completed_payload(
                run=completion,
                summary=placeholder_summary,
                paths=paths_snapshot,
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
            type_="run.completed",
            payload=self._run_completed_payload(
                run=completion,
                summary=placeholder_summary,
                paths=paths_snapshot,
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

        try:
            async for event in self._supervisor.stream(
                run.id,
                generator=generator,
            ):
                if isinstance(event, RunExecutionResult):
                    completion = await self._complete_run(
                        run,
                        status=event.status,
                        exit_code=event.return_code,
                        summary=event.summary_json,
                        error_message=event.error_message,
                    )
                    yield await self._emit_api_event(
                        run=completion,
                        type_="run.completed",
                        payload=self._run_completed_payload(
                            run=completion,
                            summary=event.summary_model,
                            paths=event.paths_snapshot,
                            failure_stage="run" if event.status is RunStatus.FAILED else None,
                            failure_message=event.error_message,
                        ),
                    )
                    continue
                forwarded = await self._event_dispatcher.emit(
                    type=event.type,
                    source=event.source or "engine",
                    workspace_id=str(run.workspace_id),
                    configuration_id=str(run.configuration_id),
                    run_id=str(run.id),
                    build_id=(
                        str(event.build_id or getattr(run, "build_id", None))
                        if (event.build_id or getattr(run, "build_id", None))
                        else None
                    ),
                    payload=event.payload,
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
                status=RunStatus.CANCELED,
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
                status=RunStatus.CANCELED,
                exit_code=None,
                summary=summary_json,
                error_message="Run execution cancelled",
            )
            yield await self._emit_api_event(
                run=completion,
                type_="run.completed",
                payload=self._run_completed_payload(
                    run=completion,
                    summary=placeholder_summary,
                    paths=paths_snapshot,
                    failure_stage="run",
                    failure_code="run_cancelled",
                    failure_message=completion.error_message,
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
                type_="run.completed",
                payload=self._run_completed_payload(
                    run=completion,
                    summary=placeholder_summary,
                    paths=paths_snapshot,
                    failure_stage="run",
                    failure_code="engine_error",
                    failure_message=completion.error_message,
                ),
            )
            return

    # --------------------------------------------------------------------- #
    # Internal helpers: DB, storage, builds
    # --------------------------------------------------------------------- #

    async def _require_run(self, run_id: str) -> Run:
        run = await self._runs.get(run_id)
        if run is None:
            logger.warning(
                "run.require_run.not_found",
                extra=log_context(run_id=run_id),
            )
            raise RunNotFoundError(run_id)
        return run

    async def _require_document(self, *, workspace_id: str, document_id: str) -> Document:
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

    def _storage_for(self, workspace_id: str) -> DocumentStorage:
        base = workspace_documents_root(self._settings, workspace_id)
        return DocumentStorage(base)

    async def _stage_input_document(
        self,
        *,
        workspace_id: str,
        document_id: str,
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

    async def _resolve_configuration(self, configuration_id: str) -> Configuration:
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

    async def _ensure_config_env_ready(
        self,
        configuration: Configuration,
        *,
        force_rebuild: bool = False,
    ) -> tuple[Path, str]:
        logger.debug(
            "run.env.ensure.start",
            extra=log_context(
                workspace_id=configuration.workspace_id,
                configuration_id=configuration.id,
                force_rebuild=force_rebuild,
            ),
        )
        options = BuildCreateOptions(force=force_rebuild, wait=True)
        build, context = await self._builds_service.prepare_build(
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            options=options,
        )
        await self._builds_service.run_to_completion(context=context, options=options)
        build = await self._builds_service.get_build_or_raise(
            build.id, workspace_id=configuration.workspace_id
        )
        if build.status is not BuildStatus.ACTIVE:
            message = build.error_message or f"Configuration {configuration.id} build failed"
            raise RunEnvironmentNotReadyError(message)
        venv_path = await self._builds_service.ensure_local_env(build=build)
        return venv_path, build.id

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
        run.canceled_at = utc_now() if status is RunStatus.CANCELED else None
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
            env["ADE_TELEMETRY_CORRELATION_ID"] = context.run_id
            env["ADE_RUN_ID"] = context.run_id
        return env

    def _run_dir_for_run(self, *, workspace_id: str, run_id: str) -> Path:
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
    def _generate_run_id() -> str:
        return str(uuid.uuid7())

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

    async def _emit_api_event(
        self,
        *,
        run: Run,
        type_: str,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        build_id: str | None = None,
    ) -> AdeEvent:
        """Emit an AdeEvent originating from the API orchestrator."""

        build_identifier = build_id or getattr(run, "build_id", None)
        event = await self._event_dispatcher.emit(
            type=type_,
            source="api",
            workspace_id=str(run.workspace_id),
            configuration_id=str(run.configuration_id),
            run_id=str(run.id),
            build_id=str(build_identifier) if build_identifier else None,
            payload=payload,
        )
        self._log_event_debug(event, origin="api")
        return event

    def event_log_reader(self, *, workspace_id: str, run_id: str) -> RunEventLogReader:
        """Return a reader for persisted run events."""

        return RunEventLogReader(
            storage=self._event_storage,
            workspace_id=workspace_id,
            run_id=run_id,
        )

    def subscribe_to_events(self, run_id: str):
        """Expose dispatcher subscription for live event streaming."""

        return self._event_dispatcher.subscribe(run_id)

    @property
    def settings(self) -> Settings:
        """Expose the bound settings instance for caller reuse."""

        return self._settings
