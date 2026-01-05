"""Service encapsulating configuration build queueing and metadata."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.events import EventRecord, EventRecordLog
from ade_api.common.ids import generate_uuid7
from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.logging import log_context
from ade_api.common.time import utc_now
from ade_api.common.types import OrderBy
from ade_api.common.validators import normalize_utc
from ade_api.features.builds.fingerprint import (
    compute_build_fingerprint,
    compute_engine_source_digest,
)
from ade_api.features.configs.deps import compute_dependency_digest
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.configs.storage import ConfigStorage
from ade_api.infra.storage import build_venv_root
from ade_api.models import Build, BuildStatus, Configuration
from ade_api.settings import Settings

from .exceptions import BuildNotFoundError, BuildWorkspaceMismatchError
from .repository import BuildsRepository
from .schemas import BuildCreateOptions, BuildLinks, BuildPage, BuildResource

__all__ = [
    "BuildDecision",
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


class BuildsService:
    """Coordinate build persistence and queueing for the API."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        storage: ConfigStorage,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
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
        workspace_id: UUID,
        configuration_id: UUID,
        options: BuildCreateOptions,
        reason: str | None = None,
    ) -> Build:
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
            reason=decision_reason,
        )
        await self._session.commit()

        logger.info(
            "build.prepare.resolved",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                build_id=resolution.build.id,
                decision=resolution.decision.value,
            ),
        )
        return resolution.build

    async def list_builds(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by: OrderBy,
        page: int,
        per_page: int,
    ) -> BuildPage:
        """Return paginated builds for ``configuration_id``."""

        logger.debug(
            "build.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                filters=[item.model_dump() for item in filters],
                join_operator=join_operator.value,
                q=q,
                page=page,
                per_page=per_page,
            ),
        )

        await self._require_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        page_result = await self._builds.list_by_configuration(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            filters=filters,
            join_operator=join_operator,
            q=q,
            order_by=order_by,
            page=page,
            per_page=per_page,
        )
        resources = [self.to_resource(build) for build in page_result.items]
        response = BuildPage(
            items=resources,
            page=page_result.page,
            per_page=page_result.per_page,
            page_count=page_result.page_count,
            total=page_result.total,
            changes_cursor=page_result.changes_cursor,
        )

        logger.info(
            "build.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                page=response.page,
                per_page=response.per_page,
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
        log = self.event_log_reader(
            workspace_id=build.workspace_id,
            configuration_id=build.configuration_id,
            build_id=build.id,
        )
        for event in log.iter(after_sequence=after_sequence):
            events.append(event)
            if len(events) >= limit:
                seq = event.get("sequence")
                next_after = int(seq) if isinstance(seq, int) else None
                break
        return events, next_after

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
    ) -> EventRecordLog:
        path = self.get_event_log_path(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
        )
        return EventRecordLog(path=str(path))

    def get_event_log_path(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
    ) -> Path:
        """Return the NDJSON log path for a build (may not exist yet)."""
        build_dir = build_venv_root(
            self._settings,
            str(workspace_id),
            str(configuration_id),
            str(build_id),
        )
        return build_dir / "logs" / "events.ndjson"

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
        engine_spec = self._settings.engine_spec
        engine_version_hint = self._resolve_engine_version(engine_spec)
        engine_source_digest = compute_engine_source_digest(engine_spec)
        fingerprint = compute_build_fingerprint(
            config_digest=config_digest,
            engine_spec=engine_spec,
            engine_version=engine_version_hint,
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
            ),
        )
        return BuildSpec(
            workspace_id=workspace_id,
            configuration_id=configuration.id,
            config_path=config_path,
            config_digest=config_digest,
            engine_spec=engine_spec,
            engine_version_hint=engine_version_hint,
            fingerprint=fingerprint,
        )

    async def _resolve_build(
        self,
        *,
        configuration: Configuration,
        spec: BuildSpec,
        options: BuildCreateOptions,
        reason: str | None,
    ) -> _BuildResolution:
        build, _created = await self._get_or_create_build(
            configuration=configuration,
            spec=spec,
            reason=reason,
        )

        configuration.content_digest = spec.config_digest
        await self._session.flush()

        if build.status in (BuildStatus.FAILED, BuildStatus.CANCELLED):
            build = await self._reset_build(build)

        if options.force and build.status is BuildStatus.READY:
            build = await self._reset_build(build)

        if build.status is BuildStatus.READY and not options.force:
            await self._sync_active_pointer(configuration, build, spec.fingerprint)
            return _BuildResolution(
                build=build,
                decision=BuildDecision.REUSE_READY,
                spec=spec,
                reason=reason,
                reuse_summary="Reused existing build",
            )

        decision = (
            BuildDecision.JOIN_INFLIGHT
            if build.status is BuildStatus.BUILDING
            else BuildDecision.START_NEW
        )

        return _BuildResolution(
            build=build,
            decision=decision,
            spec=spec,
            reason=reason,
            reuse_summary=None,
        )

    async def _get_or_create_build(
        self,
        *,
        configuration: Configuration,
        spec: BuildSpec,
        reason: str | None,
    ) -> tuple[Build, bool]:
        existing = await self._builds.get_by_fingerprint(
            configuration_id=configuration.id,
            fingerprint=spec.fingerprint,
        )
        if existing:
            return existing, False

        try:
            build = await self._create_build(
                configuration=configuration,
                spec=spec,
                reason=reason,
            )
        except IntegrityError:
            await self._session.rollback()
            fallback = await self._builds.get_by_fingerprint(
                configuration_id=configuration.id,
                fingerprint=spec.fingerprint,
            )
            if fallback is None:
                raise
            return fallback, False

        return build, True

    async def _reset_build(self, build: Build) -> Build:
        build.status = BuildStatus.QUEUED
        build.started_at = None
        build.finished_at = None
        build.exit_code = None
        build.error_message = None
        build.summary = None
        await self._session.commit()
        await self._session.refresh(build)
        return build

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

    def _epoch_seconds(self, dt: datetime | None) -> int | None:
        if dt is None:
            return None
        normalized = normalize_utc(dt)
        return int(normalized.timestamp()) if normalized else None

    def _generate_build_id(self) -> UUID:
        return generate_uuid7()
