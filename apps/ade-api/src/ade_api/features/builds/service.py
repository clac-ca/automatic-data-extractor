"""Service encapsulating configuration build orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.events import (
    EventRecord,
    new_event_record,
)
from ade_api.common.ids import generate_uuid7
from ade_api.common.logging import log_context
from ade_api.common.pagination import Page
from ade_api.common.time import utc_now
from ade_api.common.validators import normalize_utc
from ade_api.features.builds.fingerprint import (
    compute_build_fingerprint,
    compute_engine_source_digest,
)
from ade_api.features.configs.deps import compute_dependency_digest
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.runs.event_stream import (
    RunEventContext,
    RunEventStream,
    RunEventStreamRegistry,
)
from ade_api.infra.storage import (
    build_venv_marker_path,
    build_venv_path,
    build_venv_root,
)
from ade_api.models import Build, BuildStatus, Configuration
from ade_api.settings import Settings

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
    "BuildDecision",
    "BuildExecutionContext",
    "BuildNotFoundError",
    "BuildsService",
]

logger = logging.getLogger(__name__)
event_logger = logging.getLogger("ade_api.builds.events")

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

    # Shared across service instances to avoid duplicate build runners.
    _global_build_tasks: dict[UUID, asyncio.Task] = {}

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        storage: ConfigStorage,
        builder: VirtualEnvironmentBuilder | None = None,
        now: Callable[[], datetime] = utc_now,
        event_streams: RunEventStreamRegistry | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._builder = builder or VirtualEnvironmentBuilder()
        self._configs = ConfigurationsRepository(session)
        self._builds = BuildsRepository(session)
        self._now = now
        self._hydration_locks: dict[tuple[UUID, UUID, UUID], asyncio.Lock] = {}
        # Process-wide registry to avoid duplicate runners across service instances.
        self._build_tasks = self._global_build_tasks
        self._event_streams = event_streams or RunEventStreamRegistry()

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
        """Ensure a build record exists for a run (does not execute the build)."""

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
    ) -> AsyncIterator[EventRecord]:
        timeout_seconds = context.timeout_seconds or float(
            self._settings.build_timeout.total_seconds()
        )
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

        try:
            async with asyncio.timeout(timeout_seconds):
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
                    async for event in self.stream_build_events(
                        build=build,
                        start_sequence=queued_event.get("sequence") if queued_event else None,
                        timeout_seconds=timeout_seconds,
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
                    payload={"status": "building", "reason": reason},
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
                                payload={
                                    "scope": "build",
                                    "stream": event.stream,
                                    "level": "warning" if event.stream == "stderr" else "info",
                                    "message": event.message,
                                },
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
        except TimeoutError:
            build = await self._require_build(context.build_id)
            timeout_message = f"Build timed out after {timeout_seconds:.0f}s"
            await self._handle_failure(
                build=build,
                context=context,
                error=timeout_message,
            )
            build = await self._require_build(build.id)
            yield await self._emit_event(
                build=build,
                type_="build.complete",
                payload=self._build_completed_payload(
                    build=build,
                    duration_ms=None,
                    reason="timeout",
                    should_build=False,
                    reuse_summary=timeout_message,
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
    ) -> tuple[list[EventRecord], int | None]:
        """Return telemetry events for ``build_id`` with optional paging."""

        build = await self._require_build(build_id)
        events: list[EventRecord] = []
        next_after: int | None = None
        stream = self.event_log_reader(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
        )
        for event in stream.iter_persisted(after_sequence=after_sequence):
            events.append(event)
            if len(events) >= limit:
                seq = event.get("sequence")
                next_after = int(seq) if isinstance(seq, int) else None
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
            venv_path = build_venv_path(
                self._settings,
                build.workspace_id,
                build.configuration_id,
                build.id,
            )
            marker_path = build_venv_marker_path(
                self._settings,
                build.workspace_id,
                build.configuration_id,
                build.id,
            )
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
            await self._builder.build(
                build_id=build.id,
                workspace_id=build.workspace_id,
                configuration_id=build.configuration_id,
                venv_root=venv_root,
                config_path=config_path,
                engine_spec=build.engine_spec or self._settings.engine_spec,
                pip_cache_dir=(
                    Path(self._settings.pip_cache_dir) if self._settings.pip_cache_dir else None
                ),
                python_bin=build.python_interpreter or self._resolve_python_interpreter(),
                timeout=float(self._settings.build_timeout.total_seconds()),
                fingerprint=build.fingerprint or "",
            )

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

    async def get_build_or_raise(self, build_id: UUID, workspace_id: UUID | None = None) -> Build:
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
    ) -> RunEventStream:
        return self._event_stream_for_build(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
        )

    def subscribe_to_events(self, build: Build):
        return self._event_stream_for_build(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
        ).subscribe()

    def iter_events(self, *, build: Build, after_sequence: int | None = None):
        """Yield persisted events for a build."""

        return self.event_log_reader(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
        ).iter_persisted(after_sequence=after_sequence)

    async def launch_build_if_needed(
        self,
        *,
        build: Build,
        reason: str | None = None,
        run_id: UUID | None = None,
    ) -> None:
        """Start asynchronous execution for a queued/building build if not already running.

        This decouples build execution from request background tasks and allows
        queued builds to self-start when referenced (e.g., by runs or SSE consumers).
        """

        if build.status in (BuildStatus.READY, BuildStatus.FAILED, BuildStatus.CANCELLED):
            return

        if build.id in self._build_tasks:
            task = self._build_tasks.get(build.id)
            if task and not task.done():
                return

        async def _run_detached() -> None:
            from ade_api.db.session import get_sessionmaker
            from ade_api.features.configs.storage import ConfigStorage

            session_factory = get_sessionmaker(settings=self._settings)
            async with session_factory() as session:
                detached_service = BuildsService(
                    session=session,
                    settings=self._settings,
                    storage=ConfigStorage(settings=self._settings),
                    event_streams=self._event_streams,
                )
                detached_build = await detached_service._require_build(build.id)
                if detached_build.status in (
                    BuildStatus.READY,
                    BuildStatus.FAILED,
                    BuildStatus.CANCELLED,
                ):
                    return
                ctx = await detached_service._context_for_existing_build(
                    build=detached_build,
                    reason=reason,
                    run_id=run_id,
                )
                opts = BuildCreateOptions(force=False, wait=True)
                await detached_service.run_to_completion(context=ctx, options=opts)

        task = asyncio.create_task(_run_detached())
        self._build_tasks[build.id] = task

    def _build_event_context(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
        run_id: UUID | None = None,
    ) -> RunEventContext:
        return RunEventContext(
            job_id=str(run_id) if run_id else None,
            workspace_id=str(workspace_id),
            build_id=str(build_id),
            configuration_id=str(configuration_id),
        )

    def _event_stream_for_build(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
        run_id: UUID | None = None,
    ) -> RunEventStream:
        build_dir = build_venv_root(
            self._settings,
            str(workspace_id),
            str(configuration_id),
            str(build_id),
        )
        path = build_dir / "logs" / "events.ndjson"
        context = self._build_event_context(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            run_id=run_id,
        )
        return self._event_streams.get_stream(path=path, context=context)

    @staticmethod
    def _log_event_debug(event: EventRecord, *, origin: str) -> None:
        if not event_logger.isEnabledFor(logging.DEBUG):
            return
        event_logger.debug("[%s] %s", origin, json.dumps(event, default=str))

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
    ) -> dict[str, Any]:
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

        return {
            "status": str(build.status.value if hasattr(build.status, "value") else build.status),
            "failure": failure,
            "execution": execution or None,
            "artifacts": artifacts or None,
            "summary": summary_value,
        }

    async def _emit_event(
        self,
        *,
        build: Build,
        type_: str,
        payload: dict[str, Any] | Any | None = None,
        run_id: UUID | None = None,
    ) -> EventRecord:
        stream = self._event_stream_for_build(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
            run_id=run_id,
        )
        payload_dict: dict[str, Any] = {}
        if payload is not None:
            if hasattr(payload, "model_dump"):
                payload_dict = payload.model_dump(exclude_none=True)  # type: ignore[assignment]
            elif isinstance(payload, dict):
                payload_dict = payload
            else:
                payload_dict = dict(payload)

        event = new_event_record(
            event=type_,
            data=payload_dict,
        )
        appended = await stream.append(event)
        self._log_event_debug(appended, origin="build")
        return appended

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
    ) -> EventRecord | None:
        """Ensure the first event for a build is persisted."""

        stream = self._event_stream_for_build(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
            run_id=run_id,
        )
        last_cursor = stream.last_cursor()
        if last_cursor > 0:
            return next(iter(stream.iter_persisted(after_sequence=0)), None)
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
        config_digest = compute_dependency_digest(config_path)
        configuration.content_digest = config_digest
        python_interpreter = self._resolve_python_interpreter()
        python_version = await self._python_version(python_interpreter)
        engine_spec = self._settings.engine_spec
        engine_version_hint = self._resolve_engine_version(engine_spec)
        engine_source_digest = compute_engine_source_digest(engine_spec)
        fingerprint = compute_build_fingerprint(
            config_digest=config_digest,
            engine_spec=engine_spec,
            engine_version=engine_version_hint,
            python_version=python_version,
            python_bin=python_interpreter,
            extra={"engine_source_digest": engine_source_digest} if engine_source_digest else {},
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

    async def _context_for_existing_build(
        self,
        *,
        build: Build,
        reason: str | None,
        run_id: UUID | None,
    ) -> BuildExecutionContext:
        """Rehydrate a BuildExecutionContext from a persisted Build row."""

        config_path = await self._storage.ensure_config_path(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
        )

        return BuildExecutionContext(
            build_id=build.id,
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            config_path=str(config_path),
            venv_root=str(
                build_venv_root(
                    self._settings,
                    build.workspace_id,
                    build.configuration_id,
                    build.id,
                )
            ),
            python_bin=build.python_interpreter or self._resolve_python_interpreter(),
            engine_spec=build.engine_spec or self._settings.engine_spec,
            engine_version_hint=build.engine_version
            or self._resolve_engine_version(self._settings.engine_spec),
            pip_cache_dir=str(self._settings.pip_cache_dir)
            if self._settings.pip_cache_dir
            else None,
            timeout_seconds=float(self._settings.build_timeout.total_seconds()),
            decision=BuildDecision.START_NEW
            if build.status is BuildStatus.QUEUED
            else BuildDecision.JOIN_INFLIGHT,
            fingerprint=build.fingerprint,
            reason=reason,
            run_id=run_id,
            reuse_summary=None,
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
        # 1) Fast path: reuse ready build with matching fingerprint unless forced.
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

        # 2) If a matching inflight build exists, either join it or claim it.
        inflight = await self._builds.get_inflight_by_fingerprint(
            configuration_id=configuration.id,
            fingerprint=spec.fingerprint,
        )
        if inflight and self._is_stale(inflight):
            await self._fail_stale_build(inflight)
            inflight = None
        if inflight:
            decision = (
                BuildDecision.START_NEW
                if inflight.status is BuildStatus.QUEUED
                else BuildDecision.JOIN_INFLIGHT
            )
            if not allow_inflight and decision is BuildDecision.JOIN_INFLIGHT:
                raise BuildAlreadyInProgressError(
                    "Build in progress for "
                    f"workspace={spec.workspace_id} configuration={configuration.id}"
                )
            return _BuildResolution(
                build=inflight,
                decision=decision,
                spec=spec,
                reason=reason,
                reuse_summary=(
                    "Joined inflight build" if decision is BuildDecision.JOIN_INFLIGHT else None
                ),
            )

        # 3) If another inflight build exists with a different fingerprint, block unless allowed.
        inflight_other = await self._builds.get_latest_inflight(configuration_id=configuration.id)
        if inflight_other and self._is_stale(inflight_other):
            await self._fail_stale_build(inflight_other)
            inflight_other = None
        if inflight_other and inflight_other.fingerprint != spec.fingerprint:
            if not allow_inflight:
                raise BuildAlreadyInProgressError(
                    "Build in progress for "
                    f"workspace={spec.workspace_id} configuration={configuration.id}"
                )
            # Otherwise join the existing inflight build rather than spawning another.
            return _BuildResolution(
                build=inflight_other,
                decision=(
                    BuildDecision.START_NEW
                    if inflight_other.status is BuildStatus.QUEUED
                    else BuildDecision.JOIN_INFLIGHT
                ),
                spec=spec,
                reason=reason,
                reuse_summary="Joined inflight build",
            )

        # 4) Otherwise create a fresh build record.
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

    async def stream_build_events(
        self,
        *,
        build: Build,
        start_sequence: int | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[EventRecord]:
        """Yield persisted and live events for ``build`` until completion."""

        reader = self.event_log_reader(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
        )
        last_sequence = start_sequence or 0
        for event in reader.iter_persisted(after_sequence=start_sequence or 0):
            yield event
            seq = event.get("sequence")
            if isinstance(seq, int):
                last_sequence = seq
            if event.get("event") in {"build.complete", "build.failed"}:
                return

        # If the build is already terminal but no terminal event was replayed (e.g. missing log),
        # avoid blocking on an empty subscription.
        refreshed = await self._require_build(build.id)
        if refreshed.status not in (BuildStatus.QUEUED, BuildStatus.BUILDING):
            return

        timeout_ctx = (
            asyncio.timeout(timeout_seconds)
            if timeout_seconds and timeout_seconds > 0
            else nullcontext()
        )
        async with timeout_ctx:
            async with self.subscribe_to_events(build) as subscription:
                async for live_event in subscription:
                    seq = live_event.get("sequence")
                    if isinstance(seq, int) and seq <= last_sequence:
                        continue
                    yield live_event
                    if isinstance(seq, int):
                        last_sequence = seq
                    if live_event.get("event") in {"build.complete", "build.failed"}:
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

    def _resolve_engine_version(self, spec: str) -> str | None:
        path = Path(spec)
        if path.exists() and path.is_dir():
            pyproject = path / "pyproject.toml"
            try:
                data = pyproject.read_text(encoding="utf-8")
            except OSError:
                return None
            import tomllib
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
        reuse_summary = resolution.reuse_summary or (
            "Reused existing build" if resolution.decision is BuildDecision.REUSE_READY else None
        )

        return BuildExecutionContext(
            build_id=resolution.build.id,
            workspace_id=spec.workspace_id,
            configuration_id=spec.configuration_id,
            config_path=str(spec.config_path),
            venv_root=str(
                build_venv_root(
                    self._settings,
                    spec.workspace_id,
                    spec.configuration_id,
                    resolution.build.id,
                )
            ),
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

    # ------------------------------------------------------------------ #
    # Staleness detection / recovery
    # ------------------------------------------------------------------ #

    def _is_stale(self, build: Build) -> bool:
        """Return True if a build has exceeded the configured timeout window."""

        horizon = normalize_utc(self._now()) - self._settings.build_timeout
        started_or_created = normalize_utc(build.started_at or build.created_at)
        return started_or_created < horizon if started_or_created else False

    async def _fail_stale_build(
        self, build: Build, *, reason: str = "Stale build timed out"
    ) -> None:
        if build.status not in (BuildStatus.QUEUED, BuildStatus.BUILDING):
            return
        if not self._is_stale(build):
            return
        build.finished_at = self._now()
        build.exit_code = 1
        build.error_message = reason
        build.status = BuildStatus.FAILED
        await self._session.commit()
        logger.warning(
            "build.mark_stale_failed",
            extra=log_context(
                workspace_id=build.workspace_id,
                configuration_id=build.configuration_id,
                build_id=build.id,
                reason=reason,
            ),
        )

    def _epoch_seconds(self, dt: datetime | None) -> int | None:
        if dt is None:
            return None
        normalized = normalize_utc(dt)
        return int(normalized.timestamp()) if normalized else None

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
        if build.engine_version and payload.get("engine_version") != build.engine_version:
            return False
        return True

    def _generate_build_id(self) -> UUID:
        return generate_uuid7()
