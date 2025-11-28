"""Service encapsulating configuration build orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ade_engine.schemas import AdeEvent
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.builds.fingerprint import compute_build_fingerprint
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.models import Configuration
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage, compute_config_digest
from ade_api.settings import Settings
from ade_api.shared.core.logging import log_context
from ade_api.shared.core.time import utc_now
from ade_api.storage_layout import build_venv_root

from .builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderLogEvent,
    BuilderStepEvent,
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
    BuildCreateOptions,
    BuildLogEntry,
    BuildLogsResponse,
    BuildResource,
    BuildStatusLiteral,
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
    venv_root: str
    python_bin: str | None
    engine_spec: str
    engine_version_hint: str | None
    pip_cache_dir: str | None
    timeout_seconds: float
    should_run: bool
    fingerprint: str
    reuse_summary: str | None = None

    def as_dict(self) -> dict[str, str | bool | None | float]:
        return {
            "build_id": self.build_id,
            "configuration_id": self.configuration_id,
            "workspace_id": self.workspace_id,
            "config_path": self.config_path,
            "venv_root": self.venv_root,
            "python_bin": self.python_bin,
            "engine_spec": self.engine_spec,
            "engine_version_hint": self.engine_version_hint,
            "pip_cache_dir": self.pip_cache_dir,
            "timeout_seconds": self.timeout_seconds,
            "should_run": self.should_run,
            "fingerprint": self.fingerprint,
            "reuse_summary": self.reuse_summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str | bool | None | float]) -> BuildExecutionContext:
        return cls(
            build_id=str(payload["build_id"]),
            configuration_id=str(payload["configuration_id"]),
            workspace_id=str(payload["workspace_id"]),
            config_path=str(payload["config_path"]),
            venv_root=str(payload["venv_root"]),
            python_bin=payload.get("python_bin") or None,
            engine_spec=str(payload["engine_spec"]),
            engine_version_hint=payload.get("engine_version_hint") or None,
            pip_cache_dir=payload.get("pip_cache_dir") or None,
            timeout_seconds=float(payload["timeout_seconds"]),
            should_run=bool(payload["should_run"]),
            fingerprint=str(payload["fingerprint"]),
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
        self._hydration_locks: dict[str, asyncio.Lock] = {}

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
        logger.debug(
            "build.prepare.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                force=options.force,
                wait=options.wait,
            ),
        )

        configuration = await self._require_configuration(workspace_id, configuration_id)
        config_path = await self._storage.ensure_config_path(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        config_digest = compute_config_digest(config_path)
        python_interpreter = self._resolve_python_interpreter()
        python_version = await self._python_version(python_interpreter)
        engine_spec = self._settings.engine_spec
        engine_version_hint = self._resolve_engine_version(engine_spec)
        fingerprint = compute_build_fingerprint(
            config_digest=config_digest,
            engine_spec=engine_spec,
            engine_version=engine_version_hint,
            python_version=python_version,
            python_bin=python_interpreter,
            extra={},
        )

        logger.debug(
            "build.prepare.fingerprint",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                fingerprint=fingerprint,
                engine_spec=engine_spec,
                engine_version=engine_version_hint,
                python_bin=python_interpreter,
            ),
        )

        if (
            not options.force
            and configuration.active_build_status is BuildStatus.ACTIVE
            and configuration.active_build_fingerprint == fingerprint
            and configuration.active_build_id
        ):
            build = await self._require_build(configuration.active_build_id)
            context = self._reuse_context(
                build=build,
                configuration=configuration,
                config_path=config_path,
                python_interpreter=python_interpreter,
                engine_spec=engine_spec,
                engine_version_hint=engine_version_hint,
                fingerprint=fingerprint,
            )
            logger.info(
                "build.prepare.reuse",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    build_id=build.id,
                    reuse_summary=context.reuse_summary,
                ),
            )
            return build, context

        if (
            configuration.active_build_status is BuildStatus.BUILDING
            and configuration.active_build_id
            and not options.force
        ):
            if options.wait:
                logger.debug(
                    "build.prepare.wait_existing",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        build_id=configuration.active_build_id,
                    ),
                )
                await self._wait_for_build(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                )
                return await self.prepare_build(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    options=BuildCreateOptions(force=options.force, wait=False),
                )
            logger.warning(
                "build.prepare.already_in_progress",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    build_status=str(configuration.active_build_status),
                ),
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
            config_digest=config_digest,
            python_version=python_version,
            fingerprint=fingerprint,
        )
        await self._session.commit()

        logger.info(
            "build.prepare.plan_created",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                build_id=plan.build.id,
                should_rebuild=True,
            ),
        )
        return plan.build, plan.context

    async def stream_build(
        self,
        *,
        context: BuildExecutionContext,
        options: BuildCreateOptions,
    ) -> AsyncIterator[AdeEvent]:
        logger.debug(
            "build.stream.start",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=context.build_id,
                should_run=context.should_run,
                force=options.force,
            ),
        )

        build = await self._require_build(context.build_id)
        reason = "force_rebuild" if options.force else "dirty_or_missing"

        yield self._ade_event(
            build=build,
            type_="build.created",
            payload={
                "status": "queued",
                "reason": reason,
                "should_build": context.should_run,
                "engine_spec": context.engine_spec,
                "engine_version_hint": context.engine_version_hint,
                "python_bin": context.python_bin,
            },
        )

        if not context.should_run:
            logger.info(
                "build.stream.reuse_short_circuit",
                extra=log_context(
                    workspace_id=context.workspace_id,
                    configuration_id=context.configuration_id,
                    build_id=context.build_id,
                    reason="reuse_ok",
                ),
            )
            build = await self._complete_build(
                build,
                status=BuildStatus.ACTIVE,
                summary=context.reuse_summary,
                exit_code=0,
            )
            yield self._ade_event(
                build=build,
                type_="build.completed",
                payload={
                    "status": "active",
                    "summary": build.summary,
                    "exit_code": build.exit_code,
                    "env": {
                        "reason": "reuse_ok",
                        "should_build": False,
                        "force": bool(options.force),
                    },
                },
            )
            return

        build = await self._transition_status(build, BuildStatus.BUILDING)
        logger.info(
            "build.stream.started",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=build.id,
                reason=reason,
            ),
        )
        yield self._ade_event(
            build=build,
            type_="build.started",
            payload={
                "status": "building",
                "reason": reason,
            },
        )

        artifacts: BuildArtifacts | None = None
        try:
            async for event in self._builder.build_stream(
                build_id=context.build_id,
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                venv_root=Path(context.venv_root),
                config_path=Path(context.config_path),
                engine_spec=context.engine_spec,
                pip_cache_dir=Path(context.pip_cache_dir)
                if context.pip_cache_dir
                else None,
                python_bin=context.python_bin,
                timeout=context.timeout_seconds,
                fingerprint=context.fingerprint,
            ):
                if isinstance(event, BuilderStepEvent):
                    yield self._ade_event(
                        build=build,
                        type_="build.phase.started",
                        payload={
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
                        type_="build.console",
                        payload={
                            "stream": event.stream,
                            "level": "warning" if event.stream == "stderr" else "info",
                            "message": event.message,
                            "created": self._epoch_seconds(log.created_at),
                        },
                    )
                elif isinstance(event, BuilderArtifactsEvent):
                    artifacts = event.artifacts
        except BuildExecutionError as exc:
            logger.error(
                "build.stream.execution_error",
                extra=log_context(
                    workspace_id=context.workspace_id,
                    configuration_id=context.configuration_id,
                    build_id=context.build_id,
                    error=str(exc),
                ),
            )
            await self._handle_failure(
                build=build,
                context=context,
                error=str(exc),
            )
            build = await self._require_build(build.id)
            yield self._ade_event(
                build=build,
                type_="build.completed",
                payload={
                    "status": self._status_literal(build.status),
                    "exit_code": build.exit_code,
                    "summary": build.summary,
                    "error": {"message": build.error_message} if build.error_message else None,
                },
            )
            return

        if artifacts is None:
            logger.error(
                "build.stream.missing_artifacts",
                extra=log_context(
                    workspace_id=context.workspace_id,
                    configuration_id=context.configuration_id,
                    build_id=context.build_id,
                ),
            )
            await self._handle_failure(
                build=build,
                context=context,
                error="Build terminated without metadata",
            )
            build = await self._require_build(build.id)
            yield self._ade_event(
                build=build,
                type_="build.completed",
                payload={
                    "status": self._status_literal(build.status),
                    "exit_code": build.exit_code,
                    "summary": build.summary,
                    "error": {"message": build.error_message} if build.error_message else None,
                },
            )
            return

        build = await self._finalize_success(
            build=build,
            context=context,
            artifacts=artifacts,
        )
        duration_ms = None
        if build.started_at and build.finished_at:
            duration_ms = int((build.finished_at - build.started_at).total_seconds() * 1000)

        logger.info(
            "build.stream.completed",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=build.id,
                status=self._status_literal(build.status),
                exit_code=build.exit_code,
                duration_ms=duration_ms,
            ),
        )

        yield self._ade_event(
            build=build,
            type_="build.completed",
            payload={
                "status": self._status_literal(build.status),
                "exit_code": build.exit_code,
                "summary": build.summary,
                "duration_ms": duration_ms,
                "error": {"message": build.error_message} if build.error_message else None,
                "env": {"reason": reason},
            },
        )

    async def run_to_completion(
        self,
        *,
        context: BuildExecutionContext,
        options: BuildCreateOptions,
    ) -> None:
        logger.debug(
            "build.run_to_completion.start",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=context.build_id,
            ),
        )
        async for _ in self.stream_build(context=context, options=options):
            pass
        logger.debug(
            "build.run_to_completion.done",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=context.build_id,
            ),
        )

    async def ensure_local_env(self, *, build: Build) -> Path:
        """Ensure the local venv for ``build`` exists and matches the marker."""

        key = self._hydration_key(build)
        lock = self._hydration_locks.setdefault(key, asyncio.Lock())
        async with lock:
            venv_root = build_venv_root(
                self._settings,
                build.workspace_id,
                build.configuration_id,
                build.id,
            )
            venv_path = venv_root / ".venv"
            marker_path = venv_path / "ade_build.json"
            if self._marker_matches(marker_path, build):
                logger.info(
                    "build.env.hydrate.cache_hit",
                    extra=log_context(
                        workspace_id=build.workspace_id,
                        configuration_id=build.configuration_id,
                        build_id=build.id,
                        venv_path=str(venv_path),
                    ),
                )
                return venv_path

            logger.info(
                "build.env.hydrate.start",
                extra=log_context(
                    workspace_id=build.workspace_id,
                    configuration_id=build.configuration_id,
                    build_id=build.id,
                    venv_path=str(venv_path),
                ),
            )
            config_path = await self._storage.ensure_config_path(
                workspace_id=build.workspace_id,
                configuration_id=build.configuration_id,
            )
            async for _ in self._builder.build_stream(
                build_id=build.id,
                workspace_id=build.workspace_id,
                configuration_id=build.configuration_id,
                venv_root=venv_root,
                config_path=config_path,
                engine_spec=build.engine_spec or self._settings.engine_spec,
                pip_cache_dir=(
                    Path(self._settings.pip_cache_dir)
                    if self._settings.pip_cache_dir
                    else None
                ),
                python_bin=build.python_interpreter or self._resolve_python_interpreter(),
                timeout=float(self._settings.build_timeout.total_seconds()),
                fingerprint=build.fingerprint or "",
            ):
                # Hydration is best-effort and local-only; we intentionally do
                # not persist per-step events or logs here.
                pass

            logger.info(
                "build.env.hydrate.complete",
                extra=log_context(
                    workspace_id=build.workspace_id,
                    configuration_id=build.configuration_id,
                    build_id=build.id,
                    venv_path=str(venv_path),
                ),
            )
            return venv_path

    async def get_build(self, build_id: str) -> Build | None:
        return await self._builds.get(build_id)

    async def get_build_or_raise(self, build_id: str, workspace_id: str | None = None) -> Build:
        build = await self._builds.get(build_id)
        if build is None:
            logger.warning(
                "build.get.not_found",
                extra=log_context(build_id=build_id, workspace_id=workspace_id),
            )
            raise BuildNotFoundError(build_id)
        if workspace_id and build.workspace_id != workspace_id:
            logger.warning(
                "build.get.workspace_mismatch",
                extra=log_context(
                    build_id=build_id,
                    workspace_id=workspace_id,
                    build_workspace_id=build.workspace_id,
                ),
            )
            raise BuildWorkspaceMismatchError(build_id)
        return build

    async def get_logs(
        self,
        *,
        build_id: str,
        after_id: int | None = None,
        limit: int = DEFAULT_STREAM_LIMIT,
    ) -> BuildLogsResponse:
        logger.debug(
            "build.logs.list.start",
            extra=log_context(build_id=build_id, after_id=after_id, limit=limit),
        )
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

        logger.debug(
            "build.logs.list.success",
            extra=log_context(
                build_id=build_id,
                count=len(entries),
                next_after_id=next_after_id,
            ),
        )

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
        payload: dict[str, Any] | None = None,
    ) -> AdeEvent:
        return AdeEvent(
            type=type_,
            created_at=utc_now(),
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            run_id=None,
            build_id=build.id,
            **(payload or {}),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _require_configuration(
        self,
        workspace_id: str,
        configuration_id: str,
    ) -> Configuration:
        configuration = await self._configs.get(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        if configuration is None:
            logger.warning(
                "build.require_config.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                ),
            )
            raise ConfigurationNotFoundError(configuration_id)
        return configuration

    async def _require_build(self, build_id: str) -> Build:
        build = await self._builds.get(build_id)
        if build is None:
            logger.warning(
                "build.require_build.not_found",
                extra=log_context(build_id=build_id),
            )
            raise BuildNotFoundError(build_id)
        return build

    def _resolve_python_interpreter(self) -> str | None:
        python_bin = self._settings.python_bin
        if python_bin:
            return str(Path(python_bin).resolve())
        return None

    async def _python_version(self, python_bin: str | None) -> str | None:
        interpreter = python_bin or sys.executable
        try:
            output = await asyncio.to_thread(
                subprocess.check_output,
                [
                    interpreter,
                    "-c",
                    "import sys; print('.'.join(map(str, sys.version_info[:3])))",
                ],
                text=True,
            )
            return str(output).strip()
        except Exception:  # pragma: no cover - best-effort metadata
            logger.warning(
                "build.python_version.detect_failed",
                extra=log_context(python_bin=python_bin, interpreter=interpreter),
            )
            return None

    async def _create_build_plan(
        self,
        *,
        configuration: Configuration,
        config_path: Path,
        engine_spec: str,
        engine_version_hint: str | None,
        python_interpreter: str | None,
        config_digest: str,
        python_version: str | None,
        fingerprint: str,
    ) -> _BuildPlan:
        workspace_id = configuration.workspace_id
        now = self._now()
        configuration.active_build_status = BuildStatus.BUILDING  # type: ignore[assignment]
        configuration.active_build_started_at = now  # type: ignore[attr-defined]
        configuration.active_build_error = None  # type: ignore[attr-defined]
        configuration.active_build_fingerprint = fingerprint  # type: ignore[attr-defined]
        configuration.active_build_finished_at = None  # type: ignore[attr-defined]
        configuration.build_status = BuildStatus.BUILDING  # legacy field
        configuration.last_build_started_at = now  # type: ignore[attr-defined]
        configuration.last_build_error = None  # type: ignore[attr-defined]
        configuration.engine_spec = engine_spec  # type: ignore[attr-defined]
        configuration.engine_version = engine_version_hint  # type: ignore[attr-defined]
        configuration.python_interpreter = python_interpreter  # type: ignore[attr-defined]
        configuration.content_digest = config_digest

        build_id = self._generate_build_id()
        build = Build(
            id=build_id,
            workspace_id=workspace_id,
            configuration_id=configuration.id,
            status=BuildStatus.QUEUED,
            created_at=now,
            fingerprint=fingerprint,
            engine_spec=engine_spec,
            engine_version=engine_version_hint,
            python_version=python_version,
            python_interpreter=python_interpreter,
            config_digest=config_digest,
        )
        await self._builds.add(build)
        configuration.active_build_id = build.id  # type: ignore[attr-defined]
        configuration.last_build_id = build.id  # type: ignore[attr-defined]

        venv_root = build_venv_root(self._settings, workspace_id, configuration.id, build_id)
        context = BuildExecutionContext(
            build_id=build.id,
            workspace_id=workspace_id,
            configuration_id=configuration.id,
            config_path=str(config_path),
            venv_root=str(venv_root),
            python_bin=python_interpreter,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            pip_cache_dir=str(self._settings.pip_cache_dir)
            if self._settings.pip_cache_dir
            else None,
            timeout_seconds=float(self._settings.build_timeout.total_seconds()),
            should_run=True,
            fingerprint=fingerprint,
        )

        logger.debug(
            "build.plan.created",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration.id,
                build_id=build.id,
            ),
        )
        return _BuildPlan(build=build, context=context)

    async def _transition_status(self, build: Build, status: BuildStatus) -> Build:
        if status is BuildStatus.BUILDING:
            build.started_at = build.started_at or self._now()
        build.status = status
        await self._session.commit()
        await self._session.refresh(build)
        logger.debug(
            "build.status.transition",
            extra=log_context(
                workspace_id=build.workspace_id,
                configuration_id=build.configuration_id,
                build_id=build.id,
                status=status.value,
            ),
        )
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
        # We intentionally don't log per-line here; the engine event stream
        # already captures console output at a finer granularity.
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
            context.workspace_id,
            context.configuration_id,
        )
        configuration.active_build_status = BuildStatus.FAILED  # type: ignore[assignment]
        configuration.active_build_error = error  # type: ignore[attr-defined]
        configuration.active_build_finished_at = now  # type: ignore[attr-defined]
        configuration.build_status = BuildStatus.FAILED  # legacy
        configuration.last_build_error = error  # type: ignore[attr-defined]
        configuration.last_build_finished_at = now  # type: ignore[attr-defined]
        configuration.last_build_id = build.id  # type: ignore[attr-defined]
        await self._session.commit()

        logger.error(
            "build.failure",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=build.id,
                error=error,
            ),
        )

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
        build.engine_version = artifacts.engine_version
        build.python_version = artifacts.python_version
        configuration = await self._require_configuration(
            context.workspace_id,
            context.configuration_id,
        )
        configuration.active_build_status = BuildStatus.ACTIVE  # type: ignore[assignment]
        configuration.active_build_error = None  # type: ignore[attr-defined]
        configuration.active_build_finished_at = now  # type: ignore[attr-defined]
        configuration.active_build_id = build.id  # type: ignore[attr-defined]
        configuration.active_build_fingerprint = context.fingerprint  # type: ignore[attr-defined]
        configuration.build_status = BuildStatus.ACTIVE  # legacy field
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

        logger.info(
            "build.success",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=build.id,
                engine_version=artifacts.engine_version,
                python_version=artifacts.python_version,
            ),
        )
        return build

    async def _wait_for_build(self, *, workspace_id: str, configuration_id: str) -> None:
        deadline = self._now() + self._settings.build_ensure_wait
        logger.debug(
            "build.wait_for_existing.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                deadline=deadline.isoformat(),
            ),
        )
        while self._now() < deadline:
            configuration = await self._require_configuration(workspace_id, configuration_id)
            if configuration.active_build_status is not BuildStatus.BUILDING:
                logger.debug(
                    "build.wait_for_existing.complete",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        final_status=str(configuration.active_build_status),
                    ),
                )
                return
            await asyncio.sleep(1)
        logger.warning(
            "build.wait_for_existing.timeout",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
            ),
        )
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

    def _reuse_context(
        self,
        *,
        build: Build,
        configuration: Configuration,
        config_path: Path,
        python_interpreter: str | None,
        engine_spec: str,
        engine_version_hint: str | None,
        fingerprint: str,
    ) -> BuildExecutionContext:
        venv_root = build_venv_root(
            self._settings,
            configuration.workspace_id,
            configuration.id,
            build.id,
        )
        return BuildExecutionContext(
            build_id=build.id,
            workspace_id=configuration.workspace_id,
            configuration_id=configuration.id,
            config_path=str(config_path),
            venv_root=str(venv_root),
            python_bin=python_interpreter,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            pip_cache_dir=str(self._settings.pip_cache_dir)
            if self._settings.pip_cache_dir
            else None,
            timeout_seconds=float(self._settings.build_timeout.total_seconds()),
            should_run=False,
            fingerprint=fingerprint,
            reuse_summary="Reused existing build",
        )

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
        logger.debug(
            "build.complete",
            extra=log_context(
                workspace_id=build.workspace_id,
                configuration_id=build.configuration_id,
                build_id=build.id,
                status=status.value,
                exit_code=exit_code,
            ),
        )
        return build

    def _epoch_seconds(self, dt: datetime | None) -> int | None:
        if dt is None:
            return None
        return int(dt.timestamp())

    @staticmethod
    def _hydration_key(build: Build) -> str:
        return f"{build.workspace_id}:{build.configuration_id}:{build.id}"

    @staticmethod
    def _marker_matches(marker_path: Path, build: Build) -> bool:
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if payload.get("build_id") != build.id:
            return False
        if build.fingerprint and payload.get("fingerprint") != build.fingerprint:
            return False
        return True

    def _status_literal(self, status: BuildStatus) -> BuildStatusLiteral:
        from typing import cast

        return cast(BuildStatusLiteral, status.value)

    def _generate_build_id(self) -> str:
        return f"build_{uuid4().hex}"


@dataclass(slots=True)
class _BuildPlan:
    build: Build
    context: BuildExecutionContext
