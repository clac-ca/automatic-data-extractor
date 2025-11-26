"""Run orchestration service coordinating DB state and engine execution."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ade_engine.schemas import AdeEvent
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.builds.builder import (
    BuilderArtifactsEvent,
    VirtualEnvironmentBuilder,
)
from ade_api.features.builds.models import BuildStatus
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import compute_config_digest
from ade_api.features.documents.repository import DocumentsRepository
from ade_api.features.documents.staging import stage_document_input
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.system_settings.schemas import SafeModeStatus
from ade_api.features.system_settings.service import (
    SAFE_MODE_DEFAULT_DETAIL,
    SafeModeService,
)
from ade_api.settings import Settings
from ade_api.shared.core.time import utc_now
from ade_api.shared.pagination import Page
from ade_api.storage_layout import (
    config_venv_path,
    workspace_config_root,
    workspace_documents_root,
    workspace_run_root,
)

from .models import Run, RunLog, RunStatus
from .repository import RunsRepository
from .runner import ADEProcessRunner, StdoutFrame
from .schemas import (
    RunCompletedEvent,
    RunCreatedEvent,
    RunCreateOptions,
    RunEvent,
    RunLogEntry,
    RunLogEvent,
    RunLogsResponse,
    RunResource,
    RunStartedEvent,
    RunStatusLiteral,
)
from .supervisor import RunSupervisor

__all__ = [
    "RunArtifactMissingError",
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

DEFAULT_STREAM_LIMIT = 1000


RunStreamFrame = AdeEvent


@dataclass(slots=True)
class RunPathsSnapshot:
    """Container for run-relative output and log paths."""

    artifact_path: str | None = None
    events_path: str | None = None
    output_paths: list[str] = None  # type: ignore[assignment]
    processed_files: list[str] = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - import guard for circular dependencies
    from ade_api.features.documents.models import Document


@dataclass(slots=True, frozen=True)
class RunExecutionContext:
    """Minimal data required to execute a run outside the request scope."""

    run_id: str
    configuration_id: str
    workspace_id: str
    venv_path: str
    build_id: str
    runs_dir: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "configuration_id": self.configuration_id,
            "workspace_id": self.workspace_id,
            "venv_path": self.venv_path,
            "build_id": self.build_id,
            "runs_dir": self.runs_dir or "",
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> RunExecutionContext:
        return cls(
            run_id=payload["run_id"],
            configuration_id=payload["configuration_id"],
            workspace_id=payload["workspace_id"],
            venv_path=payload["venv_path"],
            build_id=payload["build_id"],
            runs_dir=payload.get("runs_dir") or None,
        )


class RunEnvironmentNotReadyError(RuntimeError):
    """Raised when a configuration lacks an active build to execute."""


class RunNotFoundError(RuntimeError):
    """Raised when a requested run row cannot be located."""


class RunDocumentMissingError(RuntimeError):
    """Raised when a requested input document cannot be located."""


class RunArtifactMissingError(RuntimeError):
    """Raised when a requested run artifact is unavailable."""


class RunLogsFileMissingError(RuntimeError):
    """Raised when a requested run log file cannot be read."""


class RunOutputMissingError(RuntimeError):
    """Raised when requested run outputs cannot be resolved."""


class RunInputMissingError(RuntimeError):
    """Raised when a run is attempted without required staged inputs."""


class RunsService:
    """Coordinate run persistence, execution, and serialization for the API."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        supervisor: RunSupervisor | None = None,
        safe_mode_service: SafeModeService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._configs = ConfigurationsRepository(session)
        self._runs = RunsRepository(session)
        self._supervisor = supervisor or RunSupervisor()
        self._documents = DocumentsRepository(session)
        self._safe_mode_service = safe_mode_service
        self._builder = VirtualEnvironmentBuilder()

        if settings.documents_dir is None:
            raise RuntimeError("ADE_DOCUMENTS_DIR is not configured")
        if settings.runs_dir is None:
            raise RuntimeError("ADE_RUNS_DIR is not configured")

        self._runs_dir = Path(settings.runs_dir)

    # ---------------------------------------------------------------------
    # Run lifecycle helpers
    # ---------------------------------------------------------------------
    async def prepare_run(
        self,
        *,
        configuration_id: str,
        options: RunCreateOptions,
    ) -> tuple[Run, RunExecutionContext]:
        """Create the queued run row and return its execution context."""

        configuration = await self._resolve_configuration(configuration_id)
        input_document_id = options.input_document_id or None
        document_descriptor: dict[str, Any] | None = None
        if input_document_id:
            document = await self._require_document(
                workspace_id=configuration.workspace_id,
                document_id=input_document_id,
            )
            document_descriptor = self._document_descriptor(document)
        venv_path, build_id = await self._ensure_config_env_ready(
            configuration, force_rebuild=options.force_rebuild
        )

        selected_sheet_name = options.input_sheet_name
        if not selected_sheet_name and options.input_sheet_names:
            if len(options.input_sheet_names) == 1:
                selected_sheet_name = options.input_sheet_names[0]

        run_id = self._generate_run_id()
        run = Run(
            id=run_id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            configuration_version_id=str(configuration.configuration_version)
            if configuration.configuration_version is not None
            else None,
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
        configuration.last_used_at = utc_now()  # type: ignore[attr-defined]
        await self._session.flush()

        await self._session.commit()
        await self._session.refresh(run)

        runs_root = workspace_run_root(self._settings, configuration.workspace_id)
        venv_path = config_venv_path(self._settings, configuration.workspace_id, configuration.id)
        context = RunExecutionContext(
            run_id=run.id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            venv_path=str(venv_path),
            build_id=build_id or "",
            runs_dir=str(runs_root),
        )
        return run, context

    async def run_to_completion(
        self,
        *,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> None:
        """Execute the run, exhausting the event stream."""

        async for _ in self.stream_run(context=context, options=options):
            pass

    async def stream_run(
        self,
        *,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> AsyncIterator[RunStreamFrame]:
        """Iterate through run events while executing the engine."""

        run = await self._require_run(context.run_id)
        yield self._ade_event(
            run=run,
            type_="run.created",
            run_payload={
                "status": self._status_literal(run.status),
                "options": options.model_dump(),
            },
        )

        run = await self._transition_status(run, RunStatus.RUNNING)
        yield self._ade_event(
            run=run,
            type_="run.started",
            run_payload={"status": self._status_literal(run.status)},
        )

        mode_message = self._format_mode_message(options)
        if mode_message:
            log = await self._append_log(run.id, mode_message, stream="stdout")
            yield self._ade_event(
                run=run,
                type_="run.log.delta",
                log_payload={"stream": "stdout", "message": mode_message, "created": self._epoch_seconds(log.created_at)},
            )

        if options.validate_only:
            completion = await self._complete_run(
                run,
                status=RunStatus.SUCCEEDED,
                exit_code=0,
                summary="Validation-only execution",
            )
            yield self._ade_event(
                run=completion,
                type_="run.completed",
                run_payload={
                    "status": self._status_literal(completion.status),
                    "mode": "validation",
                    "execution_summary": {
                        "exit_code": completion.exit_code,
                        "duration_ms": None,
                    },
                    "summary": "Validation-only execution",
                },
            )
            return

        safe_mode = await self._safe_mode_status()
        if safe_mode.enabled:
            message = f"Safe mode enabled: {safe_mode.detail}"
            log = await self._append_log(
                run.id,
                message,
                stream="stdout",
            )
            completion = await self._complete_run(
                run,
                status=RunStatus.SUCCEEDED,
                exit_code=0,
                summary="Safe mode skip",
            )
            yield self._ade_event(
                run=run,
                type_="run.log.delta",
                log_payload={"stream": "stdout", "message": message, "created": self._epoch_seconds(log.created_at)},
            )
            yield self._ade_event(
                run=completion,
                type_="run.completed",
                run_payload={
                    "status": self._status_literal(completion.status),
                    "summary": "Safe mode skip",
                },
            )
            return

        async def generator() -> AsyncIterator[RunStreamFrame]:
            execute_engine = self._execute_engine
            parameters = inspect.signature(execute_engine).parameters
            kwargs: dict[str, object] = {
                "run": run,
                "context": context,
                "options": options,
            }
            if "safe_mode_enabled" in parameters:
                kwargs["safe_mode_enabled"] = safe_mode.enabled

            async for frame in execute_engine(**kwargs):  # type: ignore[misc]
                yield frame

        try:
            async for event in self._supervisor.stream(
                run.id,
                generator=generator,
            ):
                if isinstance(event, StdoutFrame):
                    log = await self._append_log(run.id, event.message, stream=event.stream)
                    yield self._ade_event(
                        run=run,
                        type_="run.log.delta",
                        log_payload={
                            "stream": event.stream,
                            "message": event.message,
                            "created": self._epoch_seconds(log.created_at),
                        },
                    )
                    continue
                yield event
        except asyncio.CancelledError:
            completion = await self._complete_run(
                run,
                status=RunStatus.CANCELED,
                exit_code=None,
                summary="Run cancelled",
                error_message="Run execution cancelled",
            )
            yield self._ade_event(
                run=completion,
                type_="run.completed",
                run_payload={
                    "status": self._status_literal(completion.status),
                    "execution_summary": {"exit_code": completion.exit_code},
                    "error_message": completion.error_message,
                },
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("ADE run failed", extra={"run_id": run.id})
            log = await self._append_log(
                run.id,
                f"ADE run failed: {exc}",
                stream="stderr",
            )
            completion = await self._complete_run(
                run,
                status=RunStatus.FAILED,
                exit_code=None,
                error_message=str(exc),
            )
            yield self._ade_event(
                run=run,
                type_="run.log.delta",
                log_payload={
                    "stream": "stderr",
                    "message": log.message,
                    "created": self._epoch_seconds(log.created_at),
                },
            )
            yield self._ade_event(
                run=completion,
                type_="run.completed",
                run_payload={
                    "status": self._status_literal(completion.status),
                    "execution_summary": {"exit_code": completion.exit_code},
                    "error_message": completion.error_message,
                },
            )
            return

    async def get_run(self, run_id: str) -> Run | None:
        """Return the run instance for ``run_id`` if it exists."""

        return await self._runs.get(run_id)

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

        page_result = await self._runs.list_by_workspace(
            workspace_id=workspace_id,
            statuses=statuses,
            input_document_id=input_document_id,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )
        resources = [self.to_resource(run) for run in page_result.items]
        return Page(
            items=resources,
            page=page_result.page,
            page_size=page_result.page_size,
            has_next=page_result.has_next,
            has_previous=page_result.has_previous,
            total=page_result.total,
        )

    def to_resource(self, run: Run) -> RunResource:
        """Convert ``run`` into its API representation."""
        paths = self._finalize_paths(
            summary=None,
            run_dir=self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id),
            default_paths=RunPathsSnapshot(output_paths=[], processed_files=[]),
        )

        return RunResource(
            id=run.id,
            configuration_id=run.configuration_id,
            configuration_version_id=run.configuration_version_id,
            submitted_by_user_id=run.submitted_by_user_id,
            input_document_id=run.input_document_id,
            input_documents=run.input_documents or [],
            input_sheet_name=run.input_sheet_name,
            input_sheet_names=run.input_sheet_names,
            status=self._status_literal(run.status),
            attempt=run.attempt,
            retry_of_run_id=run.retry_of_run_id,
            trace_id=run.trace_id,
            created=self._epoch_seconds(run.created_at),
            started=self._epoch_seconds(run.started_at),
            finished=self._epoch_seconds(run.finished_at),
            canceled=self._epoch_seconds(run.canceled_at),
            exit_code=run.exit_code,
            artifact_uri=run.artifact_uri,
            output_uri=run.output_uri,
            logs_uri=run.logs_uri,
            summary=run.summary,
            error_message=run.error_message,
            artifact_path=paths.artifact_path,
            events_path=paths.events_path,
            output_paths=paths.output_paths or [],
            processed_files=paths.processed_files or [],
        )

    def _ade_event(
        self,
        *,
        run: Run,
        type_: str,
        run_payload: dict[str, Any] | None = None,
        build_payload: dict[str, Any] | None = None,
        env_payload: dict[str, Any] | None = None,
        validation_payload: dict[str, Any] | None = None,
        execution_payload: dict[str, Any] | None = None,
        output_delta: dict[str, Any] | None = None,
        log_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
    ) -> AdeEvent:
        return AdeEvent(
            type=type_,
            created_at=utc_now(),
            workspace_id=run.workspace_id,
            configuration_id=run.configuration_id,
            run_id=run.id,
            build_id=None,
            run=run_payload,
            build=build_payload,
            env=env_payload,
            validation=validation_payload,
            execution=execution_payload,
            output_delta=output_delta,
            log=log_payload,
            error=error_payload,
        )

    async def get_logs(
        self,
        *,
        run_id: str,
        after_id: int | None = None,
        limit: int = DEFAULT_STREAM_LIMIT,
    ) -> RunLogsResponse:
        """Return persisted log entries for ``run_id``."""

        records = await self._runs.list_logs(
            run_id=run_id,
            after_id=after_id,
            limit=limit,
        )
        entries = [self._log_to_entry(log) for log in records]
        next_after = entries[-1].id if entries and len(entries) == limit else None
        return RunLogsResponse(
            run_id=run_id,
            entries=entries,
            next_after_id=next_after,
        )

    async def get_artifact_path(self, *, run_id: str) -> Path:
        """Return the artifact path for ``run_id`` when available."""

        run = await self._require_run(run_id)
        logs_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id) / "logs"
        artifact_path = logs_dir / "artifact.json"
        if not artifact_path.is_file():
            raise RunArtifactMissingError("Run artifact is unavailable")
        return artifact_path

    async def get_logs_file_path(self, *, run_id: str) -> Path:
        """Return the raw log stream path for ``run_id`` when available."""

        run = await self._require_run(run_id)
        logs_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id) / "logs"
        logs_path = logs_dir / "events.ndjson"
        if not logs_path.is_file():
            raise RunLogsFileMissingError("Run log stream is unavailable")
        return logs_path

    async def list_output_files(self, *, run_id: str) -> list[tuple[str, int]]:
        """Return output file tuples for ``run_id``."""

        run = await self._require_run(run_id)
        output_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id) / "output"
        if not output_dir.exists() or not output_dir.is_dir():
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
        return files

    async def resolve_output_file(
        self,
        *,
        run_id: str,
        relative_path: str,
    ) -> Path:
        """Return the absolute path for ``relative_path`` in ``run_id`` outputs."""

        run = await self._require_run(run_id)
        output_dir = self._run_dir_for_run(workspace_id=run.workspace_id, run_id=run.id) / "output"
        if not output_dir.exists() or not output_dir.is_dir():
            raise RunOutputMissingError("Run output is unavailable")

        candidate = (output_dir / relative_path).resolve()
        try:
            candidate.relative_to(output_dir)
        except ValueError:
            raise RunOutputMissingError("Requested output is outside the run directory") from None

        if not candidate.is_file():
            raise RunOutputMissingError("Requested output file not found")
        return candidate

    def run_directory(self, *, workspace_id: str, run_id: str) -> Path:
        """Return the canonical run directory for a given ``run_id``."""

        return self._run_dir_for_run(workspace_id=workspace_id, run_id=run_id)

    def run_relative_path(self, path: Path) -> str:
        """Return ``path`` relative to the runs root, validating traversal."""

        root = self._runs_dir.resolve()
        candidate = path.resolve()
        try:
            return str(candidate.relative_to(root))
        except ValueError:  # pragma: no cover - defensive guard
            raise RunOutputMissingError("Requested path escapes runs directory") from None

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
            "document_id": document.id,
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
        snapshot = RunPathsSnapshot(
            artifact_path=default_paths.artifact_path,
            events_path=default_paths.events_path,
            output_paths=list(default_paths.output_paths or []),
            processed_files=list(default_paths.processed_files or []),
        )

        logs_dir = run_dir / "logs"
        artifact_candidates = [
            summary.get("artifact_path") if summary else None,
            logs_dir / "artifact.json",
        ]
        for candidate in artifact_candidates:
            snapshot.artifact_path = self._relative_if_exists(candidate)
            if snapshot.artifact_path:
                break

        event_candidates = [
            summary.get("events_path") if summary else None,
            logs_dir / "events.ndjson",
        ]
        for candidate in event_candidates:
            snapshot.events_path = self._relative_if_exists(candidate)
            if snapshot.events_path:
                break

        output_candidates = summary.get("output_paths") if summary else None
        if isinstance(output_candidates, list):
            snapshot.output_paths = [
                p
                for p in (self._relative_if_exists(path) for path in output_candidates)
                if p
            ]

        if not snapshot.output_paths:
            snapshot.output_paths = self._relative_output_paths(run_dir / "output")

        return snapshot

    @staticmethod
    def _parse_summary(line: str, default: dict[str, Any] | None = None) -> dict[str, Any] | None:
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            return default
        return candidate if isinstance(candidate, dict) else default

    @staticmethod
    def _resolve_completion(
        summary: dict[str, Any] | None, return_code: int
    ) -> tuple[RunStatus, str | None]:
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _execute_engine(
        self,
        *,
        run: Run,
        context: RunExecutionContext,
        options: RunCreateOptions,
        safe_mode_enabled: bool = False,
        ) -> AsyncIterator[RunStreamFrame]:
        python = self._resolve_python(Path(context.venv_path))
        env = self._build_env(Path(context.venv_path), options, context)
        runs_root = (
            Path(context.runs_dir)
            if context.runs_dir
            else workspace_run_root(self._settings, context.workspace_id)
        )
        run_dir = runs_root / run.id
        run_dir.mkdir(parents=True, exist_ok=True)

        if not options.input_document_id:
            raise RunInputMissingError("Input document is required for run execution")

        staged_input = await self._stage_input_document(
            workspace_id=context.workspace_id,
            document_id=options.input_document_id,
            run_dir=run_dir,
        )

        command = [str(python), "-m", "ade_engine", "run"]
        command.extend(["--input", str(staged_input)])
        command.extend(["--output-dir", str(run_dir / "output")])
        command.extend(["--logs-dir", str(run_dir / "logs")])

        sheets = options.input_sheet_names or []
        if options.input_sheet_name:
            sheets.append(options.input_sheet_name)
        for sheet in sheets:
            command.extend(["--input-sheet", sheet])

        metadata = {
            "run_id": run.id,
            "configuration_id": run.configuration_id,
            "workspace_id": run.workspace_id,
            "context_configuration_id": context.configuration_id,
        }
        for key, value in metadata.items():
            command.extend(["--metadata", f"{key}={value}"])

        if safe_mode_enabled:
            command.append("--safe-mode")

        runner = ADEProcessRunner(command=command, run_dir=run_dir, env=env)

        summary: dict[str, Any] | None = None
        paths_snapshot = RunPathsSnapshot(output_paths=[], processed_files=[])

        async for frame in runner.stream():
            if isinstance(frame, StdoutFrame):
                log = await self._append_log(run.id, frame.message, stream=frame.stream)
                summary = self._parse_summary(frame.message, default=summary)
                yield self._ade_event(
                    run=run,
                    type_="run.log.delta",
                    log_payload={
                        "stream": frame.stream,
                        "message": frame.message,
                        "created": self._epoch_seconds(log.created_at),
                    },
                )
                continue

            serialized = frame.model_dump_json()
            await self._append_log(run.id, serialized, stream="stdout")
            yield frame

        return_code = runner.returncode if runner.returncode is not None else 1
        status, error_message = self._resolve_completion(summary, return_code)

        paths_snapshot = self._finalize_paths(
            summary=summary,
            run_dir=run_dir,
            default_paths=paths_snapshot,
        )
        if summary and summary.get("processed_files"):
            paths_snapshot.processed_files = list(summary.get("processed_files", []))

        completion = await self._complete_run(
            run,
            status=status,
            exit_code=return_code,
            error_message=error_message,
        )
        yield self._ade_event(
            run=completion,
            type_="run.completed",
            run_payload={
                "status": self._status_literal(completion.status),
                "execution_summary": {"exit_code": completion.exit_code},
                "artifact_path": paths_snapshot.artifact_path,
                "events_path": paths_snapshot.events_path,
                "output_paths": paths_snapshot.output_paths,
                "processed_files": paths_snapshot.processed_files,
                "error_message": completion.error_message,
            },
        )

    async def _require_run(self, run_id: str) -> Run:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    async def _require_document(self, *, workspace_id: str, document_id: str) -> Document:
        document = await self._documents.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        if document is None:
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
            raise ConfigurationNotFoundError(configuration_id)
        if configuration.status == ConfigurationStatus.INACTIVE:
            logger.warning(
                "Launching run for inactive configuration",
                extra={"configuration_id": configuration_id},
            )
        return configuration

    async def _ensure_config_env_ready(
        self, configuration: Configuration, *, force_rebuild: bool = False
    ) -> tuple[Path, str | None]:
        config_root = workspace_config_root(
            self._settings, configuration.workspace_id, configuration.id
        )
        venv_path = config_venv_path(self._settings, configuration.workspace_id, configuration.id)
        digest = compute_config_digest(config_root)
        dirty = (
            not venv_path.exists()
            or configuration.build_status is not BuildStatus.ACTIVE
            or configuration.built_content_digest != digest
            or force_rebuild
        )
        if dirty:
            await self._rebuild_configuration_env(
                configuration=configuration,
                config_root=config_root,
                venv_path=venv_path,
                digest=digest,
            )
        return venv_path, configuration.last_build_id

    async def _rebuild_configuration_env(
        self,
        *,
        configuration: Configuration,
        config_root: Path,
        venv_path: Path,
        digest: str,
    ) -> None:
        build_id = f"build_{uuid4().hex}"
        configuration.build_status = BuildStatus.BUILDING  # type: ignore[assignment]
        configuration.last_build_started_at = utc_now()  # type: ignore[attr-defined]
        configuration.last_build_error = None  # type: ignore[attr-defined]
        configuration.last_build_id = build_id  # type: ignore[attr-defined]
        await self._session.flush()

        artifacts: BuilderArtifactsEvent | None = None
        async for event in self._builder.build_stream(
            build_id=build_id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            target_path=venv_path,
            config_path=config_root,
            engine_spec=self._settings.engine_spec,
            pip_cache_dir=(
                Path(self._settings.pip_cache_dir)
                if self._settings.pip_cache_dir
                else None
            ),
            python_bin=self._settings.python_bin,
            timeout=float(self._settings.build_timeout.total_seconds()),
        ):
            if isinstance(event, BuilderArtifactsEvent):
                artifacts = event

        if artifacts is None:
            raise RunEnvironmentNotReadyError(
                f"Build for configuration {configuration.id} did not return metadata"
            )

        now = utc_now()
        configuration.build_status = BuildStatus.ACTIVE  # type: ignore[assignment]
        configuration.engine_spec = self._settings.engine_spec  # type: ignore[attr-defined]
        configuration.engine_version = artifacts.artifacts.engine_version  # type: ignore[attr-defined]
        configuration.python_version = artifacts.artifacts.python_version  # type: ignore[attr-defined]
        python_bin = (
            venv_path
            / ("Scripts" if os.name == "nt" else "bin")
            / ("python.exe" if os.name == "nt" else "python")
        )
        configuration.python_interpreter = str(python_bin)  # type: ignore[attr-defined]
        configuration.content_digest = digest
        configuration.built_content_digest = digest  # type: ignore[attr-defined]
        configuration.built_configuration_version = configuration.configuration_version  # type: ignore[attr-defined]
        configuration.last_build_finished_at = now  # type: ignore[attr-defined]
        configuration.last_build_error = None  # type: ignore[attr-defined]
        await self._session.flush()

    async def _transition_status(self, run: Run, status: RunStatus) -> Run:
        if status is RunStatus.RUNNING:
            run.started_at = run.started_at or utc_now()
        run.status = status
        await self._session.commit()
        await self._session.refresh(run)
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
        return run

    async def _append_log(self, run_id: str, message: str, *, stream: str) -> RunLog:
        log = RunLog(run_id=run_id, message=message, stream=stream)
        self._session.add(log)
        await self._session.commit()
        await self._session.refresh(log)
        return log

    def _log_to_entry(self, log: RunLog) -> RunLogEntry:
        return RunLogEntry(
            id=log.id,
            created=self._epoch_seconds(log.created_at),
            stream="stderr" if log.stream == "stderr" else "stdout",
            message=log.message,
        )

    @staticmethod
    def _resolve_python(venv_path: Path) -> Path:
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        candidate = venv_path / bin_dir / ("python.exe" if os.name == "nt" else "python")
        if not candidate.exists():
            raise FileNotFoundError(f"Python interpreter not found in {venv_path}")
        return candidate

    @staticmethod
    def _build_env(
        venv_path: Path, options: RunCreateOptions, context: RunExecutionContext
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
            env["ADE_RUN_INPUT_SHEETS"] = json.dumps(options.input_sheet_names)
            if len(options.input_sheet_names) == 1 and not options.input_sheet_name:
                env["ADE_RUN_INPUT_SHEET"] = options.input_sheet_names[0]
        if context.run_id:
            env["ADE_TELEMETRY_CORRELATION_ID"] = context.run_id
            env["ADE_RUN_ID"] = context.run_id
        return env

    def _run_dir_for_run(self, *, workspace_id: str, run_id: str) -> Path:
        root = workspace_run_root(self._settings, workspace_id).resolve()
        candidate = (root / run_id).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:  # pragma: no cover - defensive guard
            raise RunOutputMissingError("Requested path escapes runs directory") from None
        return candidate

    @staticmethod
    def _generate_run_id() -> str:
        return f"run_{uuid4().hex}"

    @staticmethod
    def _epoch_seconds(dt: datetime | None) -> int | None:
        if dt is None:
            return None
        return int(dt.timestamp())

    @staticmethod
    def _status_literal(status: RunStatus) -> RunStatusLiteral:
        return status.value  # type: ignore[return-value]

    @staticmethod
    def _format_mode_message(options: RunCreateOptions) -> str | None:
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

    @property
    def settings(self) -> Settings:
        """Expose the bound settings instance for caller reuse."""

        return self._settings
