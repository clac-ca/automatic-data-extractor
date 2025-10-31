"""Database helpers for configs and config versions."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.shared.core.time import utc_now

from .models import Config, ConfigVersion, WorkspaceConfigState

__all__ = ["ConfigsRepository"]


class ConfigsRepository:
    """Encapsulate config persistence concerns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_configs(
        self,
        *,
        workspace_id: str,
        include_deleted: bool,
    ) -> list[Config]:
        stmt = (
            select(Config)
            .where(Config.workspace_id == workspace_id)
            .options(selectinload(Config.versions))
            .order_by(Config.created_at.desc())
        )
        if not include_deleted:
            stmt = stmt.where(Config.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return list(result.scalars().unique())

    async def get_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        include_deleted: bool,
    ) -> Config | None:
        stmt: Select[tuple[Config]] = (
            select(Config)
            .where(Config.workspace_id == workspace_id, Config.id == config_id)
            .options(selectinload(Config.versions))
        )
        if not include_deleted:
            stmt = stmt.where(Config.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def get_workspace_state(self, workspace_id: str) -> WorkspaceConfigState | None:
        return await self._session.get(
            WorkspaceConfigState,
            workspace_id,
            options=[selectinload(WorkspaceConfigState.config_version)],
        )

    async def find_by_slug(self, *, workspace_id: str, slug: str) -> Config | None:
        stmt = select(Config).where(
            Config.workspace_id == workspace_id,
            Config.slug == slug,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_config(
        self,
        *,
        workspace_id: str,
        slug: str,
        title: str,
        description: str | None,
        actor_id: str | None,
    ) -> Config:
        config = Config(
            workspace_id=workspace_id,
            slug=slug,
            title=title,
            description=description,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        self._session.add(config)
        await self._session.flush()
        return config

    async def next_sequence(self, *, config_id: str) -> int:
        stmt = select(func.coalesce(func.max(ConfigVersion.sequence), 0)).where(
            ConfigVersion.config_id == config_id
        )
        result = await self._session.execute(stmt)
        sequence = result.scalar_one()
        return int(sequence) + 1

    async def create_version(
        self,
        *,
        config: Config,
        label: str | None,
        manifest: dict[str, object],
        manifest_sha256: str,
        package_sha256: str,
        package_path: str,
        config_script_api_version: str,
        actor_id: str | None,
        sequence: int | None = None,
    ) -> ConfigVersion:
        version_sequence = sequence if sequence is not None else await self.next_sequence(config_id=config.id)
        version = ConfigVersion(
            config_id=config.id,
            sequence=version_sequence,
            label=label,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            package_sha256=package_sha256,
            package_path=package_path,
            config_script_api_version=config_script_api_version,
            created_by_user_id=actor_id,
        )
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def get_version(
        self,
        *,
        config_id: str,
        config_version_id: str,
    ) -> ConfigVersion | None:
        stmt = select(ConfigVersion).where(
            ConfigVersion.config_id == config_id,
            ConfigVersion.id == config_version_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(self, config_version_id: str) -> ConfigVersion | None:
        stmt = select(ConfigVersion).options(selectinload(ConfigVersion.config)).where(
            ConfigVersion.id == config_version_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_version_sequences(self, *, config_id: str) -> list[int]:
        stmt = select(ConfigVersion.sequence).where(ConfigVersion.config_id == config_id)
        result = await self._session.execute(stmt)
        return [int(value) for value in result.scalars().all()]

    async def touch_workspace_state(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        actor_id: str | None,
    ) -> WorkspaceConfigState:
        state = await self._session.get(WorkspaceConfigState, workspace_id)
        now = utc_now()
        if state is None:
            state = WorkspaceConfigState(
                workspace_id=workspace_id,
                config_id=config_id,
                config_version_id=config_version_id,
                updated_by_user_id=actor_id,
                created_at=now,
                updated_at=now,
            )
            self._session.add(state)
        else:
            state.config_id = config_id
            state.config_version_id = config_version_id
            state.updated_by_user_id = actor_id
            state.updated_at = now
        await self._session.flush()
        return state

    async def clear_workspace_state(self, workspace_id: str, actor_id: str | None) -> None:
        state = await self._session.get(WorkspaceConfigState, workspace_id)
        if state is None:
            return
        state.config_id = None
        state.config_version_id = None
        state.updated_by_user_id = actor_id
        state.updated_at = utc_now()
        await self._session.flush()

    async def archive_config(self, config: Config, actor_id: str | None) -> None:
        config.deleted_at = utc_now()
        config.deleted_by_user_id = actor_id
        config.updated_by_user_id = actor_id
        await self._session.flush()

    async def restore_config(self, config: Config, actor_id: str | None) -> None:
        config.deleted_at = None
        config.deleted_by_user_id = None
        config.updated_by_user_id = actor_id
        await self._session.flush()

    async def archive_version(self, version: ConfigVersion, actor_id: str | None) -> None:
        version.deleted_at = utc_now()
        version.deleted_by_user_id = actor_id
        await self._session.flush()

    async def restore_version(self, version: ConfigVersion, actor_id: str | None) -> None:
        version.deleted_at = None
        version.deleted_by_user_id = None
        await self._session.flush()
