"""Run orchestration service coordinating DB state and engine execution."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ade_engine.schemas import TelemetryEnvelope
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.builds.models import ConfigurationBuild, ConfigurationBuildStatus
from ade_api.features.builds.repository import ConfigurationBuildsRepository
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.settings import Settings
from ade_api.shared.core.time import utc_now

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
    "RunExecutionContext",
    "RunEnvironmentNotReadyError",
    "RunNotFoundError",
    "RunsService",
    "RunStreamFrame",
]

logger = logging.getLogger(__name__)

DEFAULT_STREAM_LIMIT = 1000


RunStreamFrame = RunEvent | TelemetryEnvelope


@dataclass(slots=True, frozen=True)
class RunExecutionContext:
    """Minimal data required to execute a run outside the request scope."""

    run_id: str
    configuration_id: str
    workspace_id: str
    config_id: str
    venv_path: str
    build_id: str
    job_id: str | None = None
    jobs_dir: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "configuration_id": self.configuration_id,
            "workspace_id": self.workspace_id,
            "config_id": self.config_id,
            "venv_path": self.venv_path,
            "build_id": self.build_id,
            "job_id": self.job_id or "",
            "jobs_dir": self.jobs_dir or "",
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> RunExecutionContext:
        return cls(
            run_id=payload["run_id"],
            configuration_id=payload["configuration_id"],
            workspace_id=payload["workspace_id"],
            config_id=payload["config_id"],
            venv_path=payload["venv_path"],
            build_id=payload["build_id"],
            job_id=payload.get("job_id") or None,
            jobs_dir=payload.get("jobs_dir") or None,
        )


class RunEnvironmentNotReadyError(RuntimeError):
    """Raised when a configuration lacks an active build to execute."""


class RunNotFoundError(RuntimeError):
    """Raised when a requested run row cannot be located."""


class RunsService:
    """Coordinate run persistence, execution, and serialization for the API."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        supervisor: RunSupervisor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._configs = ConfigurationsRepository(session)
        self._builds = ConfigurationBuildsRepository(session)
        self._runs = RunsRepository(session)
        self._supervisor = supervisor or RunSupervisor()

    # ---------------------------------------------------------------------
    # Run lifecycle helpers
    # ---------------------------------------------------------------------
    async def prepare_run(
        self,
        *,
        config_id: str,
        options: RunCreateOptions,
        job_id: str | None = None,
        jobs_dir: Path | None = None,
    ) -> tuple[Run, RunExecutionContext]:
        """Create the queued run row and return its execution context."""

        configuration = await self._resolve_configuration(config_id)
        build = await self._resolve_active_build(configuration)

        run = Run(
            id=self._generate_run_id(),
            configuration_id=configuration.id,
            workspace_id=configuration.workspace_id,
            config_id=configuration.config_id,
            status=RunStatus.QUEUED,
        )
        self._session.add(run)
        await self._session.flush()

        await self._builds.update_last_used(
            workspace_id=configuration.workspace_id,
            config_id=configuration.config_id,
            build_id=build.build_id,
            last_used_at=utc_now(),
        )
        await self._session.commit()
        await self._session.refresh(run)

        context = RunExecutionContext(
            run_id=run.id,
            configuration_id=configuration.id,
            workspace_id=configuration.workspace_id,
            config_id=configuration.config_id,
            venv_path=build.venv_path,
            build_id=build.build_id,
            job_id=job_id,
            jobs_dir=str(jobs_dir or self._settings.jobs_dir),
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
        yield RunCreatedEvent(
            run_id=run.id,
            created=self._epoch_seconds(run.created_at),
            status=self._status_literal(run.status),
            config_id=run.config_id,
        )

        run = await self._transition_status(run, RunStatus.RUNNING)
        yield RunStartedEvent(
            run_id=run.id,
            created=self._epoch_seconds(run.started_at),
        )

        mode_message = self._format_mode_message(options)
        if mode_message:
            log = await self._append_log(run.id, mode_message, stream="stdout")
            yield RunLogEvent(
                run_id=run.id,
                created=self._epoch_seconds(log.created_at),
                stream="stdout",
                message=mode_message,
            )

        if options.validate_only:
            completion = await self._complete_run(
                run,
                status=RunStatus.SUCCEEDED,
                exit_code=0,
                summary="Validation-only execution",
            )
            yield RunCompletedEvent(
                run_id=completion.id,
                created=self._epoch_seconds(completion.finished_at),
                status=self._status_literal(completion.status),
                exit_code=completion.exit_code,
                error_message=completion.error_message,
            )
            return

        if self._settings.safe_mode:
            log = await self._append_log(
                run.id,
                "ADE safe mode enabled; skipping engine execution.",
                stream="stdout",
            )
            completion = await self._complete_run(
                run,
                status=RunStatus.SUCCEEDED,
                exit_code=0,
                summary="Safe mode skip",
            )
            yield RunLogEvent(
                run_id=run.id,
                created=self._epoch_seconds(log.created_at),
                stream="stdout",
                message=log.message,
            )
            yield RunCompletedEvent(
                run_id=completion.id,
                created=self._epoch_seconds(completion.finished_at),
                status=self._status_literal(completion.status),
                exit_code=completion.exit_code,
                error_message=completion.error_message,
            )
            return

        async def generator() -> AsyncIterator[RunStreamFrame]:
            async for frame in self._execute_engine(
                run=run,
                context=context,
                options=options,
            ):
                yield frame

        try:
            async for event in self._supervisor.stream(
                run.id,
                generator=generator,
            ):
                yield event
        except asyncio.CancelledError:
            completion = await self._complete_run(
                run,
                status=RunStatus.CANCELED,
                exit_code=None,
                summary="Run cancelled",
                error_message="Run execution cancelled",
            )
            yield RunCompletedEvent(
                run_id=completion.id,
                created=self._epoch_seconds(completion.finished_at),
                status=self._status_literal(completion.status),
                exit_code=completion.exit_code,
                error_message=completion.error_message,
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
            yield RunLogEvent(
                run_id=run.id,
                created=self._epoch_seconds(log.created_at),
                stream="stderr",
                message=log.message,
            )
            yield RunCompletedEvent(
                run_id=completion.id,
                created=self._epoch_seconds(completion.finished_at),
                status=self._status_literal(completion.status),
                exit_code=completion.exit_code,
                error_message=completion.error_message,
            )
            return

    async def get_run(self, run_id: str) -> Run | None:
        """Return the run instance for ``run_id`` if it exists."""

        return await self._runs.get(run_id)

    def to_resource(self, run: Run) -> RunResource:
        """Convert ``run`` into its API representation."""

        return RunResource(
            id=run.id,
            config_id=run.config_id,
            status=self._status_literal(run.status),
            created=self._epoch_seconds(run.created_at),
            started=self._epoch_seconds(run.started_at),
            finished=self._epoch_seconds(run.finished_at),
            exit_code=run.exit_code,
            summary=run.summary,
            error_message=run.error_message,
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _execute_engine(
        self,
        *,
        run: Run,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> AsyncIterator[RunStreamFrame]:
        python = self._resolve_python(Path(context.venv_path))
        env = self._build_env(Path(context.venv_path), options, context)
        job_id = context.job_id or run.id
        jobs_root = Path(context.jobs_dir or self._settings.jobs_dir)
        job_dir = jobs_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(python),
            "-m",
            "ade_engine",
            "--job-id",
            job_id,
            "--jobs-dir",
            str(jobs_root),
        ]
        if self._settings.safe_mode:
            command.append("--safe-mode")

        runner = ADEProcessRunner(command=command, job_dir=job_dir, env=env)

        async for frame in runner.stream():
            if isinstance(frame, StdoutFrame):
                log = await self._append_log(run.id, frame.message, stream=frame.stream)
                yield RunLogEvent(
                    run_id=run.id,
                    created=self._epoch_seconds(log.created_at),
                    stream=frame.stream,
                    message=frame.message,
                )
                continue

            serialized = frame.model_dump_json()
            await self._append_log(run.id, serialized, stream="stdout")
            yield frame

        return_code = runner.returncode if runner.returncode is not None else 1
        status = RunStatus.SUCCEEDED if return_code == 0 else RunStatus.FAILED
        error_message = (
            None if status is RunStatus.SUCCEEDED else f"Process exited with {return_code}"
        )
        completion = await self._complete_run(
            run,
            status=status,
            exit_code=return_code,
            error_message=error_message,
        )
        yield RunCompletedEvent(
            run_id=completion.id,
            created=self._epoch_seconds(completion.finished_at),
            status=self._status_literal(completion.status),
            exit_code=completion.exit_code,
            error_message=completion.error_message,
        )

    async def _require_run(self, run_id: str) -> Run:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    async def _resolve_configuration(self, config_id: str) -> Configuration:
        configuration = await self._configs.get_by_config_id(config_id)
        if configuration is None:
            raise ConfigurationNotFoundError(config_id)
        if configuration.status == ConfigurationStatus.INACTIVE:
            logger.warning(
                "Launching run for inactive configuration", extra={"config_id": config_id}
            )
        return configuration

    async def _resolve_active_build(self, configuration: Configuration) -> ConfigurationBuild:
        build = await self._builds.get_active(
            workspace_id=configuration.workspace_id,
            config_id=configuration.config_id,
        )
        if build is None or build.status is not ConfigurationBuildStatus.ACTIVE:
            raise RunEnvironmentNotReadyError(
                f"Configuration {configuration.config_id} does not have an active build"
            )
        return build

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
        if context.run_id:
            env["ADE_TELEMETRY_CORRELATION_ID"] = context.run_id
            env["ADE_RUN_ID"] = context.run_id
        return env

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

    @property
    def settings(self) -> Settings:
        """Expose the bound settings instance for caller reuse."""

        return self._settings
