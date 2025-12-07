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
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.ids import generate_uuid7
from ade_api.common.logging import log_context
from ade_api.common.pagination import Page
from ade_api.common.time import utc_now
from ade_api.core.models import Build, BuildStatus, Configuration
from ade_api.features.builds.fingerprint import compute_build_fingerprint
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage, compute_config_digest
from ade_api.infra.storage import build_venv_root
from ade_api.schemas.events import (
    AdeEvent,
    AdeEventPayload,
    BuildCompletedPayload,
    BuildStartedPayload,
    ConsoleLinePayload,
)
from ade_api.settings import Settings

from .builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    VirtualEnvironmentBuilder,
)
from .emitters import BuildEventEmitter
from .event_dispatcher import BuildEventDispatcher, BuildEventLogReader, BuildEventStorage
from .exceptions import (
    BuildAlreadyInProgressError,
    BuildExecutionError,
    BuildNotFoundError,
    BuildWorkspaceMismatchError,
)
from .repository import BuildsRepository
from .schemas import BuildCreateOptions, BuildLinks, BuildResource

__all__ = [
    "BuildDecision",
    "BuildExecutionContext",
    "BuildNotFoundError",
    "BuildsService",
]

logger = logging.getLogger(__name__)

DEFAULT_EVENTS_PAGE_LIMIT = 1000


@dataclass(slots=True, frozen=True)
class BuildSpec:
    """Immutable build inputs used to compute a fingerprint."""

    workspace_id: UUID
    configuration_id: UUID
    config_path: Path
    config_digest: str
    engine_spec: str
    engine_version_hint: str | None
    python_bin: str | None
    python_version: str | None
    fingerprint: str


class BuildDecision(StrEnum):
    REUSE_READY = "reuse_ready"
    JOIN_INFLIGHT = "join_inflight"
    START_NEW = "start_new"


@dataclass(slots=True, frozen=True)
class _BuildResolution:
    build: Build
    decision: BuildDecision
    spec: BuildSpec
    reason: str | None
    reuse_summary: str | None = None


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
    decision: BuildDecision
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
            "decision": self.decision.value,
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
            decision=BuildDecision(str(payload["decision"])),
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
        decision_reason = reason or ("force_rebuild" if options.force else "on_demand")
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
        spec = await self._build_spec(
            configuration=configuration,
            workspace_id=workspace_id,
        )
        resolution = await self._resolve_build(
            configuration=configuration,
            spec=spec,
            options=options,
            allow_inflight=allow_inflight,
            reason=decision_reason,
        )
        context = self._build_execution_context(
            resolution=resolution,
            run_id=run_id,
        )
        await self._session.commit()

        logger.info(
            "build.prepare.resolved",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                build_id=resolution.build.id,
                decision=resolution.decision.value,
                reuse_summary=context.reuse_summary,
            ),
        )
        if resolution.decision in (BuildDecision.JOIN_INFLIGHT, BuildDecision.START_NEW):
            await self._ensure_build_queued_event(
                build=resolution.build,
                reason=decision_reason,
                should_build=resolution.decision is BuildDecision.START_NEW,
                engine_spec=spec.engine_spec,
                engine_version_hint=spec.engine_version_hint,
                python_bin=spec.python_bin,
                run_id=run_id,
            )
        return resolution.build, context

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
        decision = context.decision
        logger.debug(
            "build.stream.start",
            extra=log_context(
                workspace_id=context.workspace_id,
                configuration_id=context.configuration_id,
                build_id=context.build_id,
                decision=decision.value,
                force=options.force,
            ),
        )

        build = await self._require_build(context.build_id)
        summary: str | None = build.summary or context.reuse_summary
        reason = context.reason or ("force_rebuild" if options.force else "on_demand")

        queued_event = await self._ensure_build_queued_event(
            build=build,
            reason=reason,
            should_build=decision is BuildDecision.START_NEW,
            engine_spec=context.engine_spec,
            engine_version_hint=context.engine_version_hint,
            python_bin=context.python_bin,
            run_id=context.run_id,
        )
        if queued_event:
            yield queued_event

        if decision is BuildDecision.REUSE_READY:
            logger.info(
                "build.stream.reuse_short_circuit",
                extra=log_context(
                    workspace_id=context.workspace_id,
                    configuration_id=context.configuration_id,
                    build_id=context.build_id,
                    reason="reuse_ok",
                ),
            )
            yield await self._emit_event(
                build=build,
                type_="build.complete",
                payload=self._build_completed_payload(
                    build=build,
                    reason="reuse_ok",
                    should_build=False,
                    reuse_summary=summary,
                    engine_spec=context.engine_spec,
                    engine_version_hint=context.engine_version_hint,
                    python_bin=context.python_bin,
                ),
                run_id=context.run_id,
            )
            return
        if decision is BuildDecision.JOIN_INFLIGHT:
            logger.info(
                "build.stream.join_inflight",
                extra=log_context(
                    workspace_id=context.workspace_id,
                    configuration_id=context.configuration_id,
                    build_id=context.build_id,
                ),
            )
            async for event in self._stream_existing_and_live_events(
                build=build,
                start_sequence=queued_event.sequence if queued_event else None,
            ):
                yield event
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
            type_="build.start",
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
                        type_="build.phase.start",
                        payload={
                            "phase": event.step.value,
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
                type_="build.complete",
                payload=self._build_completed_payload(
                    build=build,
                    duration_ms=None,
                    reason="reuse_ok",
                    should_build=False,
                    reuse_summary=summary,
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
                type_="build.complete",
                payload=self._build_completed_payload(build=build),
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
            type_="build.complete",
            payload=self._build_completed_payload(
                build=build,
                duration_ms=duration_ms,
                reason=reason,
                engine_spec=context.engine_spec,
                engine_version_hint=context.engine_version_hint,
                python_bin=context.python_bin,
            ),
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

    def _build_completed_payload(
        self,
        *,
        build: Build,
        duration_ms: int | None = None,
        reason: str | None = None,
        should_build: bool | None = None,
        engine_spec: str | None = None,
        engine_version_hint: str | None = None,
        python_bin: str | None = None,
        reuse_summary: str | None = None,
    ) -> BuildCompletedPayload:
        execution: dict[str, Any] = {}
        if build.exit_code is not None:
            execution["exit_code"] = build.exit_code
        if duration_ms is not None:
            execution["duration_ms"] = duration_ms

        context: dict[str, Any] = {}
        if reason:
            context["reason"] = reason
        if should_build is not None:
            context["should_build"] = should_build
        if engine_spec:
            context["engine_spec"] = engine_spec
        if engine_version_hint:
            context["engine_version_hint"] = engine_version_hint
        if python_bin:
            context["python_bin"] = python_bin
        if reuse_summary:
            context["reuse_summary"] = reuse_summary

        artifacts: dict[str, Any] = {}
        summary_value = build.summary or reuse_summary
        if summary_value:
            artifacts["summary"] = summary_value
        if context:
            artifacts["context"] = context

        failure = {"message": build.error_message} if build.error_message else None

        return BuildCompletedPayload(
            status=str(build.status.value if hasattr(build.status, "value") else build.status),
            failure=failure,
            execution=execution or None,
            artifacts=artifacts or None,
            summary=summary_value,
        )

    async def _emit_event(
        self,
        *,
        build: Build,
        type_: str,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        run_id: UUID | None = None,
    ) -> AdeEvent:
        emitter = BuildEventEmitter(
            self._event_dispatcher,
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
            run_id=run_id,
        )
        return await emitter.emit(type=type_, payload=payload or {})

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
                k: v
                for k, v in {
                    "status": "queued",
                    "reason": reason,
                    "should_build": should_build,
                    "engine_spec": engine_spec,
                    "engine_version_hint": engine_version_hint,
                    "python_bin": python_bin,
                }.items()
                if v is not None
            },
            run_id=run_id,
        )

    async def _build_spec(
        self,
        *,
        configuration: Configuration,
        workspace_id: UUID,
    ) -> BuildSpec:
        config_path = await self._storage.ensure_config_path(
            workspace_id=workspace_id,
            configuration_id=configuration.id,
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
                configuration_id=configuration.id,
                fingerprint=fingerprint,
                engine_spec=engine_spec,
                engine_version=engine_version_hint,
                python_bin=python_interpreter,
            ),
        )
        return BuildSpec(
            workspace_id=workspace_id,
            configuration_id=configuration.id,
            config_path=config_path,
            config_digest=config_digest,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            python_bin=python_interpreter,
            python_version=python_version,
            fingerprint=fingerprint,
        )

    async def _resolve_build(
        self,
        *,
        configuration: Configuration,
        spec: BuildSpec,
        options: BuildCreateOptions,
        allow_inflight: bool,
        reason: str | None,
    ) -> _BuildResolution:
        if not options.force:
            ready_build = await self._find_ready_build_match(
                configuration=configuration,
                fingerprint=spec.fingerprint,
            )
            if ready_build:
                await self._sync_active_pointer(configuration, ready_build, spec.fingerprint)
                return _BuildResolution(
                    build=ready_build,
                    decision=BuildDecision.REUSE_READY,
                    spec=spec,
                    reason=reason,
                    reuse_summary="Reused existing build",
                )

        inflight = None
        if not options.force:
            inflight = await self._builds.get_inflight_by_fingerprint(
                configuration_id=configuration.id,
                fingerprint=spec.fingerprint,
            )
        if inflight:
            if options.wait:
                logger.debug(
                    "build.prepare.wait_existing",
                    extra=log_context(
                        workspace_id=spec.workspace_id,
                        configuration_id=configuration.id,
                        build_id=inflight.id,
                        fingerprint=spec.fingerprint,
                    ),
                )
                await self._wait_for_build(
                    workspace_id=spec.workspace_id,
                    configuration_id=configuration.id,
                    fingerprint=spec.fingerprint,
                )
                return await self._resolve_build(
                    configuration=configuration,
                    spec=spec,
                    options=BuildCreateOptions(force=options.force, wait=False),
                    allow_inflight=allow_inflight,
                    reason=reason,
                )
            if not allow_inflight:
                logger.warning(
                    "build.prepare.already_in_progress",
                    extra=log_context(
                        workspace_id=spec.workspace_id,
                        configuration_id=configuration.id,
                        build_status=str(inflight.status),
                        build_id=inflight.id,
                        fingerprint=spec.fingerprint,
                    ),
                )
                raise BuildAlreadyInProgressError(
                    "Build in progress for "
                    f"workspace={spec.workspace_id} configuration={configuration.id}"
                )
            return _BuildResolution(
                build=inflight,
                decision=BuildDecision.JOIN_INFLIGHT,
                spec=spec,
                reason=reason,
                reuse_summary="Joined inflight build",
            )

        other_inflight = await self._builds.get_latest_inflight(configuration_id=configuration.id)
        if other_inflight and other_inflight.fingerprint != spec.fingerprint:
            if options.wait:
                logger.debug(
                    "build.prepare.wait_other_inflight",
                    extra=log_context(
                        workspace_id=spec.workspace_id,
                        configuration_id=configuration.id,
                        build_id=other_inflight.id,
                        fingerprint=other_inflight.fingerprint,
                    ),
                )
                await self._wait_for_build(
                    workspace_id=spec.workspace_id,
                    configuration_id=configuration.id,
                )
                return await self._resolve_build(
                    configuration=configuration,
                    spec=spec,
                    options=BuildCreateOptions(force=options.force, wait=False),
                    allow_inflight=allow_inflight,
                    reason=reason,
                )
            if not allow_inflight:
                logger.warning(
                    "build.prepare.already_in_progress",
                    extra=log_context(
                        workspace_id=spec.workspace_id,
                        configuration_id=configuration.id,
                        build_status=str(other_inflight.status),
                        build_id=other_inflight.id,
                        fingerprint=other_inflight.fingerprint,
                    ),
                )
                raise BuildAlreadyInProgressError(
                    "Build in progress for "
                    f"workspace={spec.workspace_id} configuration={configuration.id}"
                )

        build = await self._create_build(
            configuration=configuration,
            spec=spec,
            reason=reason,
        )
        return _BuildResolution(
            build=build,
            decision=BuildDecision.START_NEW,
            spec=spec,
            reason=reason,
        )

    async def _stream_existing_and_live_events(
        self,
        *,
        build: Build,
        start_sequence: int | None = None,
    ) -> AsyncIterator[AdeEvent]:
        """Yield persisted and live events for ``build`` until completion."""

        reader = self.event_log_reader(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
        )
        last_sequence = start_sequence or 0
        for event in reader.iter(after_sequence=start_sequence or 0):
            yield event
            if event.sequence:
                last_sequence = event.sequence
            if event.type in {"build.complete", "build.failed"}:
                return

        async with self.subscribe_to_events(build.id) as subscription:
            async for live_event in subscription:
                if live_event.sequence and live_event.sequence <= last_sequence:
                    continue
                yield live_event
                if live_event.sequence:
                    last_sequence = live_event.sequence
                if live_event.type in {"build.complete", "build.failed"}:
                    break

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

    async def _create_build(
        self,
        *,
        configuration: Configuration,
        spec: BuildSpec,
        reason: str | None,
    ) -> Build:
        workspace_id = configuration.workspace_id
        now = self._now()

        build_id = self._generate_build_id()
        build = Build(
            id=build_id,
            workspace_id=workspace_id,
            configuration_id=configuration.id,
            status=BuildStatus.QUEUED,
            created_at=now,
            fingerprint=spec.fingerprint,
            engine_spec=spec.engine_spec,
            engine_version=spec.engine_version_hint,
            python_version=spec.python_version,
            python_interpreter=spec.python_bin,
            config_digest=spec.config_digest,
        )
        await self._builds.add(build)

        logger.debug(
            "build.plan.created",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration.id,
                build_id=build.id,
                reason=reason,
            ),
        )
        return build

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

    async def _wait_for_build(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        fingerprint: str | None = None,
    ) -> None:
        deadline = self._now() + self._settings.build_ensure_wait
        logger.debug(
            "build.wait_for_existing.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                deadline=deadline.isoformat(),
                fingerprint=fingerprint,
            ),
        )
        while self._now() < deadline:
            inflight = (
                await self._builds.get_inflight_by_fingerprint(
                    configuration_id=configuration_id,
                    fingerprint=fingerprint,
                )
                if fingerprint
                else await self._builds.get_latest_inflight(configuration_id=configuration_id)
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
                        fingerprint=fingerprint,
                    ),
                )
                return
            await asyncio.sleep(1)
        logger.warning(
            "build.wait_for_existing.timeout",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                fingerprint=fingerprint,
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

    async def _find_ready_build_match(
        self,
        *,
        configuration: Configuration,
        fingerprint: str,
    ) -> Build | None:
        """Return an existing ready build whose fingerprint matches ``fingerprint``."""

        if configuration.active_build_id:
            existing = await self._builds.get(configuration.active_build_id)
            if (
                existing
                and existing.status is BuildStatus.READY
                and existing.fingerprint == fingerprint
            ):
                return existing
        return await self._builds.get_ready_by_fingerprint(
            configuration_id=configuration.id,
            fingerprint=fingerprint,
        )

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

    def _build_execution_context(
        self,
        *,
        resolution: _BuildResolution,
        run_id: UUID | None,
    ) -> BuildExecutionContext:
        spec = resolution.spec
        venv_root = build_venv_root(
            self._settings,
            spec.workspace_id,
            spec.configuration_id,
            resolution.build.id,
        )
        reuse_summary = resolution.reuse_summary
        if reuse_summary is None and resolution.decision is BuildDecision.REUSE_READY:
            reuse_summary = "Reused existing build"

        return BuildExecutionContext(
            build_id=resolution.build.id,
            workspace_id=spec.workspace_id,
            configuration_id=spec.configuration_id,
            config_path=str(spec.config_path),
            venv_root=str(venv_root),
            python_bin=spec.python_bin,
            engine_spec=spec.engine_spec,
            engine_version_hint=spec.engine_version_hint,
            pip_cache_dir=str(self._settings.pip_cache_dir)
            if self._settings.pip_cache_dir
            else None,
            timeout_seconds=float(self._settings.build_timeout.total_seconds()),
            decision=resolution.decision,
            fingerprint=spec.fingerprint,
            reason=resolution.reason,
            run_id=run_id,
            reuse_summary=reuse_summary,
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
        try:
            marker_build_id = UUID(str(payload.get("build_id")))
        except (TypeError, ValueError):
            return False
        if marker_build_id != build.id:
            return False
        if build.fingerprint and payload.get("fingerprint") != build.fingerprint:
            return False
        return True

    def _generate_build_id(self) -> UUID:
        return generate_uuid7()
