"""Persistence helpers for configuration queries."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Configuration


class ConfigurationsRepository:
    """Query helper responsible for configuration lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_configurations(
        self,
        *,
        document_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[Configuration]:
        """Return configurations ordered by recency."""

        stmt: Select[tuple[Configuration]] = select(Configuration).order_by(
            Configuration.created_at.desc(),
            Configuration.id.desc(),
        )
        if document_type:
            stmt = stmt.where(Configuration.document_type == document_type)
        if is_active is not None:
            stmt = stmt.where(Configuration.is_active.is_(is_active))

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_configuration(self, configuration_id: str) -> Configuration | None:
        """Return the configuration identified by ``configuration_id`` when available."""

        return await self._session.get(Configuration, configuration_id)

    async def get_active_configuration(
        self, document_type: str
    ) -> Configuration | None:
        """Return the active configuration for ``document_type`` when present."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(
                Configuration.document_type == document_type,
                Configuration.is_active.is_(True),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_active_configurations(
        self, document_type: str | None = None
    ) -> list[Configuration]:
        """Return active configurations scoped by optional ``document_type``."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(Configuration.is_active.is_(True))
            .order_by(Configuration.document_type.asc())
        )
        if document_type:
            stmt = stmt.where(Configuration.document_type == document_type)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def determine_next_version(self, document_type: str) -> int:
        """Return the next sequential version for ``document_type``."""

        stmt = select(Configuration.version).where(
            Configuration.document_type == document_type
        )
        stmt = stmt.order_by(Configuration.version.desc()).limit(1)
        result = await self._session.execute(stmt)
        latest = result.scalars().first()
        return (latest or 0) + 1

    async def create_configuration(
        self,
        *,
        document_type: str,
        title: str,
        payload: Mapping[str, Any],
        version: int,
    ) -> Configuration:
        """Persist a configuration record."""

        configuration = Configuration(
            document_type=document_type,
            title=title,
            version=version,
            is_active=False,
            activated_at=None,
            payload=dict(payload),
        )
        self._session.add(configuration)
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def update_configuration(
        self,
        configuration: Configuration,
        *,
        title: str,
        payload: Mapping[str, Any],
    ) -> Configuration:
        """Update ``configuration`` with the provided fields."""

        configuration.title = title
        configuration.payload = dict(payload)
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def delete_configuration(self, configuration: Configuration) -> None:
        """Remove ``configuration`` from the database."""

        await self._session.delete(configuration)
        await self._session.flush()

    async def activate_configuration(
        self, configuration: Configuration
    ) -> Configuration:
        """Mark ``configuration`` as active and deactivate others for its document type."""

        await self._session.execute(
            update(Configuration)
            .where(
                Configuration.document_type == configuration.document_type,
                Configuration.id != configuration.id,
            )
            .values(is_active=False, activated_at=None)
        )

        configuration.is_active = True
        configuration.activated_at = datetime.now(tz=UTC).isoformat(
            timespec="seconds"
        )
        await self._session.flush()
        await self._session.refresh(configuration)
        return configuration

    async def get_configuration_by_version(
        self,
        *,
        document_type: str,
        version: int,
    ) -> Configuration | None:
        """Return the configuration for ``document_type`` at ``version`` when present."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(
                Configuration.document_type == document_type,
                Configuration.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()


__all__ = ["ConfigurationsRepository"]
