"""Service encapsulating configuration build orchestration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from typing import Any

from ade_engine.schemas import AdeEvent
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.models import Configuration
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.settings import Settings
from ade_api.shared.core.time import utc_now
from ade_api.storage_layout import config_venv_path

from .builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
    VirtualEnvironmentBuilder,
)
from .exceptions import (
    BuildAlreadyInProgressError,
    BuildExecutionError,
    BuildNotFoundError,
    BuildWorkspaceMismatchError,
)
from .models import Build, BuildLog, BuildStatus
from .repository import BuildsRepository
from .schemas import (
    BuildCompletedEvent,
    BuildCreatedEvent,
    BuildCreateOptions,
    BuildEvent,
    BuildLogEntry,
    BuildLogsResponse,
    BuildResource,
    BuildStatusLiteral,
)
from .schemas import (
    BuildLogEvent as BuildLogSchema,
)
from .schemas import (
    BuildStepEvent as BuildStepSchema,
)

__all__ = [
    "BuildExecutionContext",
    "BuildNotFoundError",
    "BuildsService",
]

logger = logging.getLogger(__name__)

DEFAULT_STREAM_LIMIT = 1000


@dataclass(slots=True, frozen=True)
class BuildExecutionContext:
    """Data required to execute a build outside the request scope."""

    build_id: str
    configuration_id: str
    workspace_id: str
    config_path: str
    target_path: str
    python_bin: str | None
    engine_spec: str
    pip_cache_dir: str | None
    timeout_seconds: float
    should_run: bool
    reuse_summary: str | None = None

    def as_dict(self) -> dict[str, str | bool | None | float]:
        return {
            "build_id": self.build_id,
            "configuration_id": self.configuration_id,
            "workspace_id": self.workspace_id,
            "config_path": self.config_path,
            "target_path": self.target_path,
            "python_bin": self.python_bin,
            "engine_spec": self.engine_spec,
            "pip_cache_dir": self.pip_cache_dir,
            "timeout_seconds": self.timeout_seconds,
            "should_run": self.should_run,
            "reuse_summary": self.reuse_summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str | bool | None | float]) -> BuildExecutionContext:
        return cls(
            build_id=str(payload["build_id"]),
            configuration_id=str(payload["configuration_id"]),
            workspace_id=str(payload["workspace_id"]),
            config_path=str(payload["config_path"]),
            target_path=str(payload["target_path"]),
            python_bin=payload.get("python_bin") or None,
            engine_spec=str(payload["engine_spec"]),
            pip_cache_dir=payload.get("pip_cache_dir") or None,
            timeout_seconds=float(payload["timeout_seconds"]),
            should_run=bool(payload["should_run"]),
            reuse_summary=payload.get("reuse_summary") or None,
        )


class BuildsService:
    """Coordinate build persistence, execution, and serialization."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        storage: ConfigStorage,
        builder: VirtualEnvironmentBuilder | None = None,
        now: callable[[], datetime] = utc_now,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._builder = builder or VirtualEnvironmentBuilder()
        self._configs = ConfigurationsRepository(session)
        self._builds = BuildsRepository(session)
        self._now = now

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def storage(self) -> ConfigStorage:
        return self._storage

    async def prepare_build(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        options: BuildCreateOptions,
    ) -> tuple[Build, BuildExecutionContext]:
        configuration = await self._require_configuration(workspace_id, configuration_id)
        config_path = await self._storage.ensure_config_path(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )

        python_interpreter = self._resolve_python_interpreter()
        engine_spec = self._settings.engine_spec
        engine_version_hint = self._resolve_engine_version(engine_spec)

        should_rebuild = self._should_rebuild(
            configuration=configuration,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            python_interpreter=python_interpreter,
            force=options.force,
        )

        target_path = config_venv_path(self._settings, workspace_id, configuration_id)

        if not should_rebuild:
            build = await self._create_reuse_build_row(
                configuration=configuration,
            )
            await self._session.commit()
            context = BuildExecutionContext(
                build_id=build.id,
                workspace_id=workspace_id,
                configuration_id=configuration.id,
                config_path=str(config_path),
                target_path=str(target_path),
                python_bin=python_interpreter,
                engine_spec=engine_spec,
                pip_cache_dir=str(self._settings.pip_cache_dir)
                if self._settings.pip_cache_dir
                else None,
                timeout_seconds=float(self._settings.build_timeout.total_seconds()),
                should_run=False,
                reuse_summary="Reused existing build",
            )
            return build, context

        if configuration.build_status is BuildStatus.BUILDING:
            if options.wait:
                await self._wait_for_build(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                )
                return await self.prepare_build(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    options=BuildCreateOptions(force=options.force, wait=False),
                )
            raise BuildAlreadyInProgressError(
                f"Build in progress for workspace={workspace_id} configuration={configuration_id}"
            )

        plan = await self._create_build_plan(
            configuration=configuration,
            config_path=config_path,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            python_interpreter=python_interpreter,
            target_path=target_path,
        )
        await self._session.commit()
        return plan.build, plan.context

    async def stream_build(
        self,
        *,
        context: BuildExecutionContext,
        options: BuildCreateOptions,
    ) -> AsyncIterator[AdeEvent]:
        build = await self._require_build(context.build_id)
        reason = "force_rebuild" if options.force else "dirty_or_missing"
        yield self._ade_event(
            build=build,
            type_="build.created",
            build_payload={"status": self._status_literal(build.status)},
        )
        yield self._ade_event(
            build=build,
            type_="build.plan",
            env_payload={
                "should_build": context.should_run,
                "force": bool(options.force),
                "reason": reason,
                "engine_spec": context.engine_spec,
                "engine_version_hint": context.engine_version_hint,
                "python_bin": context.python_bin,
            },
        )

        if not context.should_run:
            build = await self._complete_build(
                build,
                status=BuildStatus.ACTIVE,
                summary=context.reuse_summary,
                exit_code=0,
            )
            yield self._ade_event(
                build=build,
                type_="build.completed",
                build_payload={
                    "status": self._status_literal(build.status),
                    "exit_code": build.exit_code,
                    "summary": build.summary,
                },
                env_payload={
                    "should_build": False,
                    "force": bool(options.force),
                    "reason": "reuse_ok",
                },
            )
            return

        build = await self._transition_status(build, BuildStatus.BUILDING)
        yield self._ade_event(
            build=build,
            type_="build.progress",
            build_payload={
                "phase": BuildStep.CREATE_VENV.value,
                "message": "Starting build",
            },
        )

        artifacts: BuildArtifacts | None = None
        try:
            async for event in self._builder.build_stream(
                build_id=context.build_id,
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                target_path=Path(context.target_path),
                config_path=Path(context.config_path),
                engine_spec=context.engine_spec,
                pip_cache_dir=Path(context.pip_cache_dir)
                if context.pip_cache_dir
                else None,
                python_bin=context.python_bin,
                timeout=context.timeout_seconds,
            ):
                if isinstance(event, BuilderStepEvent):
                    yield self._ade_event(
                        build=build,
                        type_="build.progress",
                        build_payload={
                            "phase": event.step.value,
                            "message": event.message,
                        },
                    )
                elif isinstance(event, BuilderLogEvent):
                    log = await self._append_log(
                        build_id=build.id,
                        message=event.message,
                        stream=event.stream,
                    )
                    yield self._ade_event(
                        build=build,
                        type_="build.log.delta",
                        log_payload={
                            "stream": event.stream,
                            "message": event.message,
                            "created": self._epoch_seconds(log.created_at),
                        },
                    )
                elif isinstance(event, BuilderArtifactsEvent):
                    artifacts = event.artifacts
        except BuildExecutionError as exc:
            await self._handle_failure(
                build=build,
                context=context,
                error=str(exc),
            )
            build = await self._require_build(build.id)
            yield self._ade_event(
                build=build,
                type_="build.completed",
                build_payload={
                    "status": self._status_literal(build.status),
                    "exit_code": build.exit_code,
                    "summary": build.summary,
                    "error_message": build.error_message,
                },
            )
            return

        if artifacts is None:
            await self._handle_failure(
                build=build,
                context=context,
                error="Build terminated without metadata",
            )
            build = await self._require_build(build.id)
            yield self._ade_event(
                build=build,
                type_="build.completed",
                build_payload={
                    "status": self._status_literal(build.status),
                    "exit_code": build.exit_code,
                    "summary": build.summary,
                    "error_message": build.error_message,
                },
            )
            return

        build = await self._finalize_success(
            build=build,
            context=context,
            artifacts=artifacts,
        )
        yield self._ade_event(
            build=build,
            type_="build.completed",
            build_payload={
                "status": self._status_literal(build.status),
                "exit_code": build.exit_code,
                "summary": build.summary,
                "error_message": build.error_message,
            },
            env_payload={"reason": reason},
        )

    async def run_to_completion(
        self,
        *,
        context: BuildExecutionContext,
        options: BuildCreateOptions,
    ) -> None:
        async for _ in self.stream_build(context=context, options=options):
            pass

    async def get_build(self, build_id: str) -> Build | None:
        return await self._builds.get(build_id)

    async def get_build_or_raise(self, build_id: str, workspace_id: str | None = None) -> Build:
        build = await self._builds.get(build_id)
        if build is None:
            raise BuildNotFoundError(build_id)
        if workspace_id and build.workspace_id != workspace_id:
            raise BuildWorkspaceMismatchError(build_id)
        return build

    async def get_logs(
        self,
        *,
        build_id: str,
        after_id: int | None = None,
        limit: int = DEFAULT_STREAM_LIMIT,
    ) -> BuildLogsResponse:
        logs = await self._builds.list_logs(
            build_id=build_id,
            after_id=after_id,
            limit=limit,
        )
        entries = [
            BuildLogEntry(
                id=log.id,
                created=self._epoch_seconds(log.created_at),
                stream=log.stream,
                message=log.message,
            )
            for log in logs
        ]
        next_after_id = entries[-1].id if entries and len(entries) == limit else None
        return BuildLogsResponse(
            build_id=build_id,
            entries=entries,
            next_after_id=next_after_id,
        )

    def to_resource(self, build: Build) -> BuildResource:
        return BuildResource(
            id=build.id,
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            status=self._status_literal(build.status),
            created=self._epoch_seconds(build.created_at),
            started=self._epoch_seconds(build.started_at),
            finished=self._epoch_seconds(build.finished_at),
            exit_code=build.exit_code,
            summary=build.summary,
            error_message=build.error_message,
        )

    def _ade_event(
        self,
        *,
        build: Build,
        type_: str,
        build_payload: dict[str, Any] | None = None,
        env_payload: dict[str, Any] | None = None,
        log_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
    ) -> AdeEvent:
        return AdeEvent(
            type=type_,
            created_at=utc_now(),
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            run_id=None,
            build_id=build.id,
            run=None,
            build=build_payload,
            env=env_payload,
            validation=None,
            execution=None,
            output_delta=None,
            log=log_payload,
            error=error_payload,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _require_configuration(
        self, workspace_id: str, configuration_id: str
    ) -> Configuration:
        configuration = await self._configs.get(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)
        return configuration

    async def _require_build(self, build_id: str) -> Build:
        build = await self._builds.get(build_id)
        if build is None:
            raise BuildNotFoundError(build_id)
        return build

    def _resolve_python_interpreter(self) -> str | None:
        python_bin = self._settings.python_bin
        if python_bin:
            return str(Path(python_bin).resolve())
        return None

    def _should_rebuild(
        self,
        *,
        configuration: Configuration,
        engine_spec: str,
        engine_version_hint: str | None,
        python_interpreter: str | None,
        force: bool,
    ) -> bool:
        if force:
            return True
        if configuration.build_status is not BuildStatus.ACTIVE:
            return True
        reasons = [
            configuration.built_configuration_version != configuration.configuration_version,
            configuration.built_content_digest != configuration.content_digest,
            configuration.engine_spec != engine_spec,
            configuration.engine_version != engine_version_hint,
            configuration.python_interpreter != python_interpreter,
        ]
        return any(reasons)

    async def _create_reuse_build_row(
        self,
        *,
        configuration: Configuration,
    ) -> Build:
        now = self._now()
        build = Build(
            id=self._generate_build_id(),
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            status=BuildStatus.ACTIVE,
            created_at=now,
            started_at=now,
            finished_at=now,
            exit_code=0,
            summary="Reused existing build",
        )
        await self._builds.add(build)
        configuration.last_build_id = build.id  # type: ignore[attr-defined]
        return build

    async def _create_build_plan(
        self,
        *,
        configuration: Configuration,
        config_path: Path,
        engine_spec: str,
        engine_version_hint: str | None,
        python_interpreter: str | None,
        target_path: Path,
    ) -> _BuildPlan:
        workspace_id = configuration.workspace_id
        configuration.build_status = BuildStatus.BUILDING  # type: ignore[assignment]
        configuration.last_build_started_at = self._now()  # type: ignore[attr-defined]
        configuration.last_build_error = None  # type: ignore[attr-defined]
        configuration.engine_spec = engine_spec  # type: ignore[attr-defined]
        configuration.engine_version = engine_version_hint  # type: ignore[attr-defined]
        configuration.python_interpreter = python_interpreter  # type: ignore[attr-defined]

        build = Build(
            id=self._generate_build_id(),
            workspace_id=workspace_id,
            configuration_id=configuration.id,
            status=BuildStatus.QUEUED,
            created_at=self._now(),
        )
        await self._builds.add(build)
        configuration.last_build_id = build.id  # type: ignore[attr-defined]

        context = BuildExecutionContext(
            build_id=build.id,
            workspace_id=workspace_id,
            configuration_id=configuration.id,
            config_path=str(config_path),
            target_path=str(target_path),
            python_bin=python_interpreter,
            engine_spec=engine_spec,
            pip_cache_dir=str(self._settings.pip_cache_dir)
            if self._settings.pip_cache_dir
            else None,
            timeout_seconds=float(self._settings.build_timeout.total_seconds()),
            should_run=True,
        )
        return _BuildPlan(build=build, context=context)

    async def _transition_status(self, build: Build, status: BuildStatus) -> Build:
        if status is BuildStatus.BUILDING:
            build.started_at = build.started_at or self._now()
        build.status = status
        await self._session.commit()
        await self._session.refresh(build)
        return build

    async def _append_log(
        self,
        *,
        build_id: str,
        message: str,
        stream: str,
    ) -> BuildLog:
        log = BuildLog(
            build_id=build_id,
            message=message,
            stream=stream,
        )
        await self._builds.add_log(log)
        await self._session.commit()
        await self._session.refresh(log)
        return log

    async def _handle_failure(
        self,
        *,
        build: Build,
        context: BuildExecutionContext,
        error: str,
    ) -> None:
        now = self._now()
        build.status = BuildStatus.FAILED
        build.finished_at = now
        build.exit_code = 1
        build.error_message = error
        configuration = await self._require_configuration(
            context.workspace_id, context.configuration_id
        )
        configuration.build_status = BuildStatus.FAILED  # type: ignore[assignment]
        configuration.last_build_error = error  # type: ignore[attr-defined]
        configuration.last_build_finished_at = now  # type: ignore[attr-defined]
        configuration.last_build_id = build.id  # type: ignore[attr-defined]
        await self._session.commit()

    async def _finalize_success(
        self,
        *,
        build: Build,
        context: BuildExecutionContext,
        artifacts: BuildArtifacts,
    ) -> Build:
        now = self._now()
        build.status = BuildStatus.ACTIVE
        build.started_at = build.started_at or now
        build.finished_at = now
        build.exit_code = 0
        build.summary = "Build succeeded"
        configuration = await self._require_configuration(
            context.workspace_id, context.configuration_id
        )
        configuration.build_status = BuildStatus.ACTIVE  # type: ignore[assignment]
        configuration.engine_spec = context.engine_spec  # type: ignore[attr-defined]
        configuration.engine_version = artifacts.engine_version  # type: ignore[attr-defined]
        configuration.python_version = artifacts.python_version  # type: ignore[attr-defined]
        configuration.python_interpreter = context.python_bin  # type: ignore[attr-defined]
        configuration.built_configuration_version = configuration.configuration_version  # type: ignore[attr-defined]
        configuration.built_content_digest = configuration.content_digest  # type: ignore[attr-defined]
        configuration.last_build_finished_at = now  # type: ignore[attr-defined]
        configuration.last_build_error = None  # type: ignore[attr-defined]
        configuration.last_build_id = build.id  # type: ignore[attr-defined]
        await self._session.commit()
        await self._session.refresh(build)
        return build

    async def _wait_for_build(self, *, workspace_id: str, configuration_id: str) -> None:
        deadline = self._now() + self._settings.build_ensure_wait
        while self._now() < deadline:
            configuration = await self._require_configuration(workspace_id, configuration_id)
            if configuration.build_status is not BuildStatus.BUILDING:
                return
            await asyncio.sleep(1)
        raise BuildAlreadyInProgressError(
            f"Build still in progress for workspace={workspace_id} configuration={configuration_id}"
        )

    def _resolve_engine_version(self, spec: str) -> str | None:
        path = Path(spec)
        if path.exists() and path.is_dir():
            pyproject = path / "pyproject.toml"
            try:
                data = pyproject.read_text(encoding="utf-8")
            except OSError:
                return None
            try:
                import tomllib
            except ModuleNotFoundError:  # pragma: no cover - py<3.11 guard
                return None
            parsed = tomllib.loads(data)
            return parsed.get("project", {}).get("version")
        if "==" in spec:
            return spec.split("==", 1)[1]
        return None

    async def _complete_build(
        self,
        build: Build,
        *,
        status: BuildStatus,
        summary: str | None,
        exit_code: int | None,
    ) -> Build:
        now = self._now()
        build.status = status
        build.started_at = build.started_at or now
        build.finished_at = now
        build.summary = summary
        build.exit_code = exit_code
        await self._session.commit()
        await self._session.refresh(build)
        return build

    def _epoch_seconds(self, dt: datetime | None) -> int | None:
        if dt is None:
            return None
        return int(dt.timestamp())

    def _status_literal(self, status: BuildStatus) -> BuildStatusLiteral:
        from typing import cast

        return cast(BuildStatusLiteral, status.value)

    def _generate_build_id(self) -> str:
        return f"build_{uuid4().hex}"


@dataclass(slots=True)
class _BuildPlan:
    build: Build
    context: BuildExecutionContext
