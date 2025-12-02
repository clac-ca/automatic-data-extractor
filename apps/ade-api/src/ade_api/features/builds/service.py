"""Service encapsulating configuration build orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from ade_engine.schemas import (
    AdeEvent,
    AdeEventPayload,
    BuildCompletedPayload,
    BuildStartedPayload,
    ConsoleLinePayload,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.logging import log_context
from ade_api.common.pagination import Page
from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.core.models import Build, BuildStatus, Configuration
from ade_api.features.builds.fingerprint import compute_build_fingerprint
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage, compute_config_digest
from ade_api.infra.storage import build_venv_root
from ade_api.settings import Settings
from .event_dispatcher import BuildEventDispatcher, BuildEventLogReader, BuildEventStorage

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
from .repository import BuildsRepository
from .schemas import BuildCreateOptions, BuildLinks, BuildResource

__all__ = [
    "BuildExecutionContext",
    "BuildNotFoundError",
    "BuildsService",
]

logger = logging.getLogger(__name__)

DEFAULT_EVENTS_PAGE_LIMIT = 1000


@dataclass(slots=True, frozen=True)
class BuildExecutionContext:
    """Data required to execute a build outside the request scope."""

    build_id: UUID
    configuration_id: UUID
    workspace_id: UUID
    config_path: str
    venv_root: str
    python_bin: str | None
    engine_spec: str
    engine_version_hint: str | None
    pip_cache_dir: str | None
    timeout_seconds: float
    should_run: bool
    fingerprint: str
    reason: str | None = None
    run_id: UUID | None = None
    reuse_summary: str | None = None

    def as_dict(self) -> dict[str, str | bool | None | float]:
        return {
            "build_id": str(self.build_id),
            "configuration_id": str(self.configuration_id),
            "workspace_id": str(self.workspace_id),
            "config_path": self.config_path,
            "venv_root": self.venv_root,
            "python_bin": self.python_bin,
            "engine_spec": self.engine_spec,
            "engine_version_hint": self.engine_version_hint,
            "pip_cache_dir": self.pip_cache_dir,
            "timeout_seconds": self.timeout_seconds,
            "should_run": self.should_run,
            "fingerprint": self.fingerprint,
            "reason": self.reason,
            "run_id": str(self.run_id) if self.run_id else None,
            "reuse_summary": self.reuse_summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str | bool | None | float]) -> BuildExecutionContext:
        return cls(
            build_id=UUID(str(payload["build_id"])),
            configuration_id=UUID(str(payload["configuration_id"])),
            workspace_id=UUID(str(payload["workspace_id"])),
            config_path=str(payload["config_path"]),
            venv_root=str(payload["venv_root"]),
            python_bin=payload.get("python_bin") or None,
            engine_spec=str(payload["engine_spec"]),
            engine_version_hint=payload.get("engine_version_hint") or None,
            pip_cache_dir=payload.get("pip_cache_dir") or None,
            timeout_seconds=float(payload["timeout_seconds"]),
            should_run=bool(payload["should_run"]),
            fingerprint=str(payload["fingerprint"]),
            reason=payload.get("reason") or None,
            run_id=UUID(str(payload["run_id"])) if payload.get("run_id") else None,
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
        event_dispatcher: BuildEventDispatcher | None = None,
        event_storage: BuildEventStorage | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._builder = builder or VirtualEnvironmentBuilder()
        self._configs = ConfigurationsRepository(session)
        self._builds = BuildsRepository(session)
        self._now = now
        self._hydration_locks: dict[tuple[UUID, UUID, UUID], asyncio.Lock] = {}
        if event_dispatcher and event_storage is None:
            event_storage = event_dispatcher.storage
        self._event_storage = event_storage or BuildEventStorage(settings=settings)
        self._event_dispatcher = event_dispatcher or BuildEventDispatcher(
            storage=self._event_storage
        )

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
        workspace_id: UUID,
        configuration_id: UUID,
        options: BuildCreateOptions,
        allow_inflight: bool = False,
        reason: str | None = None,
        run_id: UUID | None = None,
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
        configuration.content_digest = config_digest
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

        ready_build: Build | None = None
        if configuration.active_build_id:
            existing = await self._builds.get(configuration.active_build_id)
            if (
                existing
                and existing.status is BuildStatus.READY
                and existing.fingerprint == fingerprint
            ):
                ready_build = existing
        if ready_build is None and not options.force:
            ready_build = await self._builds.get_ready_by_fingerprint(
                configuration_id=configuration.id,
                fingerprint=fingerprint,
            )

        if ready_build and not options.force:
            await self._sync_active_pointer(configuration, ready_build, fingerprint)
            context = self._reuse_context(
                build=ready_build,
                configuration=configuration,
                config_path=config_path,
                python_interpreter=python_interpreter,
                engine_spec=engine_spec,
                engine_version_hint=engine_version_hint,
                fingerprint=fingerprint,
                reason=reason,
                run_id=run_id,
            )
            await self._session.commit()
            logger.info(
                "build.prepare.reuse",
                extra=log_context(
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    build_id=ready_build.id,
                    reuse_summary=context.reuse_summary,
                ),
            )
            return ready_build, context

        inflight = await self._builds.get_latest_inflight(configuration_id=configuration.id)
        if inflight and not options.force:
            if options.wait:
                logger.debug(
                    "build.prepare.wait_existing",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        build_id=inflight.id,
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
                    allow_inflight=allow_inflight,
                    reason=reason,
                    run_id=run_id,
                )
            if not allow_inflight:
                logger.warning(
                    "build.prepare.already_in_progress",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        build_status=str(inflight.status),
                    ),
                )
                raise BuildAlreadyInProgressError(
                    f"Build in progress for workspace={workspace_id} configuration={configuration_id}"
                )
            context = self._reuse_context(
                build=inflight,
                configuration=configuration,
                config_path=config_path,
                python_interpreter=python_interpreter,
                engine_spec=engine_spec,
                engine_version_hint=engine_version_hint,
                fingerprint=fingerprint,
                should_run=False,
                reason=reason,
                run_id=run_id,
            )
            await self._ensure_build_queued_event(
                build=inflight,
                reason=reason or "on_demand",
                should_build=context.should_run,
                engine_spec=engine_spec,
                engine_version_hint=engine_version_hint,
                python_bin=python_interpreter,
                run_id=run_id,
            )
            return inflight, context

        plan = await self._create_build_plan(
            configuration=configuration,
            config_path=config_path,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            python_interpreter=python_interpreter,
            config_digest=config_digest,
            python_version=python_version,
            fingerprint=fingerprint,
            reason=reason or ("force_rebuild" if options.force else "on_demand"),
            run_id=run_id,
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
        await self._ensure_build_queued_event(
            build=plan.build,
            reason=reason or ("force_rebuild" if options.force else "on_demand"),
            should_build=plan.context.should_run,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            python_bin=python_interpreter,
            run_id=run_id,
        )
        return plan.build, plan.context

    async def ensure_build_for_run(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        force_rebuild: bool,
        run_id: UUID | None = None,
        reason: str = "on_demand",
    ) -> tuple[Build, BuildExecutionContext]:
        """Non-blocking build ensure used by run creation."""

        options = BuildCreateOptions(force=force_rebuild, wait=False)
        return await self.prepare_build(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            options=options,
            allow_inflight=True,
            reason=reason,
            run_id=run_id,
        )

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
        reason = context.reason or ("force_rebuild" if options.force else "on_demand")

        queued_event = await self._ensure_build_queued_event(
            build=build,
            reason=reason,
            should_build=context.should_run,
            engine_spec=context.engine_spec,
            engine_version_hint=context.engine_version_hint,
            python_bin=context.python_bin,
            run_id=context.run_id,
        )
        if queued_event:
            yield queued_event

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
            summary = build.summary or context.reuse_summary
            yield await self._emit_event(
                build=build,
                type_="build.completed",
                payload={
                    "status": build.status,
                    "summary": summary,
                    "exit_code": build.exit_code,
                    "env": {
                        "reason": "reuse_ok",
                        "should_build": False,
                        "force": bool(options.force),
                    },
                },
                run_id=context.run_id,
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
        yield await self._emit_event(
            build=build,
            type_="build.started",
            payload=BuildStartedPayload(status="building", reason=reason),
            run_id=context.run_id,
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
                    yield await self._emit_event(
                        build=build,
                        type_="build.progress",
                        payload={
                            "step": event.step.value,
                            "message": event.message,
                        },
                        run_id=context.run_id,
                    )
                elif isinstance(event, BuilderLogEvent):
                    yield await self._emit_event(
                        build=build,
                        type_="console.line",
                        payload=ConsoleLinePayload(
                            scope="build",
                            stream=event.stream,
                            level="warning" if event.stream == "stderr" else "info",
                            message=event.message,
                        ),
                        run_id=context.run_id,
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
            yield await self._emit_event(
                build=build,
                type_="build.completed",
                payload=BuildCompletedPayload(
                    status=build.status,
                    exit_code=build.exit_code,
                    summary=build.summary,
                    error={"message": build.error_message} if build.error_message else None,
                ),
                run_id=context.run_id,
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
            yield await self._emit_event(
                build=build,
                type_="build.completed",
                payload=BuildCompletedPayload(
                    status=build.status,
                    exit_code=build.exit_code,
                    summary=build.summary,
                    error={"message": build.error_message} if build.error_message else None,
                ),
                run_id=context.run_id,
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
                status=build.status.value,
                exit_code=build.exit_code,
                duration_ms=duration_ms,
            ),
        )

        yield await self._emit_event(
            build=build,
            type_="build.completed",
            payload={
                "status": build.status,
                "exit_code": build.exit_code,
                "summary": build.summary,
                "duration_ms": duration_ms,
                "error": {"message": build.error_message} if build.error_message else None,
                "env": {"reason": reason},
            },
            run_id=context.run_id,
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

    async def list_builds(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        statuses: Sequence[BuildStatus] | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[BuildResource]:
        """Return paginated builds for ``configuration_id``."""

        logger.debug(
            "build.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                statuses=[status.value for status in statuses] if statuses else None,
                page=page,
                page_size=page_size,
                include_total=include_total,
            ),
        )

        await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        page_result = await self._builds.list_by_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            statuses=statuses,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )
        resources = [self.to_resource(build) for build in page_result.items]
        response = Page(
            items=resources,
            page=page_result.page,
            page_size=page_result.page_size,
            has_next=page_result.has_next,
            has_previous=page_result.has_previous,
            total=page_result.total,
        )

        logger.info(
            "build.list.success",
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

    async def get_build_events(
        self,
        *,
        build_id: UUID,
        after_sequence: int | None = None,
        limit: int = DEFAULT_EVENTS_PAGE_LIMIT,
    ) -> tuple[list[AdeEvent], int | None]:
        """Return ADE telemetry events for ``build_id`` with optional paging."""

        build = await self._require_build(build_id)
        events: list[AdeEvent] = []
        next_after: int | None = None
        reader = self.event_log_reader(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
        )
        for event in reader.iter(after_sequence=after_sequence):
            events.append(event)
            if len(events) >= limit:
                next_after = event.sequence
                break
        return events, next_after

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

    async def get_build(self, build_id: UUID) -> Build | None:
        return await self._builds.get(build_id)

    async def get_build_or_raise(
        self, build_id: UUID, workspace_id: UUID | None = None
    ) -> Build:
        build = await self._builds.get(build_id)
        if build is None:
            logger.warning(
                "build.get.not_found",
                extra=log_context(build_id=build_id, workspace_id=workspace_id),
            )
            raise BuildNotFoundError(build_id)
        if workspace_id and str(build.workspace_id) != str(workspace_id):
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

    def to_resource(self, build: Build) -> BuildResource:
        return BuildResource(
            id=build.id,
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            status=build.status,
            created=self._epoch_seconds(build.created_at),
            started=self._epoch_seconds(build.started_at),
            finished=self._epoch_seconds(build.finished_at),
            exit_code=build.exit_code,
            summary=build.summary,
            error_message=build.error_message,
            links=self._links(build.id),
        )

    @staticmethod
    def _links(build_id: UUID):
        base = f"/api/v1/builds/{build_id}"
        return BuildLinks(
            self=base,
            events=f"{base}/events",
            events_stream=f"{base}/events/stream",
        )

    def event_log_reader(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
    ) -> BuildEventLogReader:
        return BuildEventLogReader(
            storage=self._event_storage,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
        )

    def subscribe_to_events(self, build_id: UUID):
        return self._event_dispatcher.subscribe(build_id)

    async def _emit_event(
        self,
        *,
        build: Build,
        type_: str,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        run_id: UUID | None = None,
    ) -> AdeEvent:
        return await self._event_dispatcher.emit(
            type=type_,
            source="api",
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            run_id=run_id,
            build_id=build.id,
            payload=payload or {},
        )

    async def _ensure_build_queued_event(
        self,
        *,
        build: Build,
        reason: str,
        should_build: bool | None = None,
        engine_spec: str | None = None,
        engine_version_hint: str | None = None,
        python_bin: str | None = None,
        run_id: UUID | None = None,
    ) -> AdeEvent | None:
        """Ensure the first event for a build is persisted."""

        last_sequence = self._event_storage.last_sequence(
            workspace_id=str(build.workspace_id),
            configuration_id=str(build.configuration_id),
            build_id=str(build.id),
        )
        if last_sequence > 0:
            reader = self.event_log_reader(
                workspace_id=str(build.workspace_id),
                configuration_id=str(build.configuration_id),
                build_id=str(build.id),
            )
            return next(iter(reader.iter(after_sequence=0)), None)
        return await self._emit_event(
            build=build,
            type_="build.queued",
            payload={
                "status": "queued",
                "reason": reason,
                "should_build": should_build,
                "engine_spec": engine_spec,
                "engine_version_hint": engine_version_hint,
                "python_bin": python_bin,
            },
            run_id=run_id,
        )
    async def _require_configuration(
        self,
        workspace_id: UUID,
        configuration_id: UUID,
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

    async def _require_build(self, build_id: UUID) -> Build:
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
        reason: str | None,
        run_id: UUID | None,
    ) -> _BuildPlan:
        workspace_id = configuration.workspace_id
        now = self._now()
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
            reason=reason,
            run_id=run_id,
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
        build.status = BuildStatus.READY
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
        await self._sync_active_pointer(configuration, build, context.fingerprint)
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

    async def _wait_for_build(self, *, workspace_id: UUID, configuration_id: UUID) -> None:
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
            inflight = await self._builds.get_latest_inflight(
                configuration_id=configuration_id
            )
            if inflight is None or inflight.status not in (
                BuildStatus.QUEUED,
                BuildStatus.BUILDING,
            ):
                logger.debug(
                    "build.wait_for_existing.complete",
                    extra=log_context(
                        workspace_id=workspace_id,
                        configuration_id=configuration_id,
                        final_status=str(inflight.status) if inflight else "none",
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

    async def _sync_active_pointer(
        self,
        configuration: Configuration,
        build: Build,
        fingerprint: str,
    ) -> None:
        configuration.active_build_id = build.id
        configuration.active_build_fingerprint = fingerprint
        if configuration.activated_at is None:
            configuration.activated_at = self._now()
        await self._session.flush()

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
        should_run: bool = False,
        reason: str | None = None,
        run_id: UUID | None = None,
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
            should_run=should_run,
            fingerprint=fingerprint,
            reason=reason,
            run_id=run_id,
            reuse_summary="Reused existing build" if not should_run else None,
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
    def _hydration_key(build: Build) -> tuple[UUID, UUID, UUID]:
        return (build.workspace_id, build.configuration_id, build.id)

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

    def _generate_build_id(self) -> UUID:
        return generate_uuid7()


@dataclass(slots=True)
class _BuildPlan:
    build: Build
    context: BuildExecutionContext
