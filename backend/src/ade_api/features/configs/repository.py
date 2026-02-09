"""Persistence helpers for workspace configurations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ade_db.models import Configuration, ConfigurationStatus


class ConfigurationsRepository:
    """Query helpers for configuration metadata."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def base_query(self) -> Select[tuple[Configuration]]:
        return select(Configuration)

    def get(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
    ) -> Configuration | None:
        stmt = (
            self
            .base_query()
            .where(
                Configuration.workspace_id == workspace_id,
                Configuration.id == configuration_id,
            )
            .limit(1)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def list_for_workspace(self, workspace_id: UUID) -> Sequence[Configuration]:
        stmt = (
            self
            .base_query()
            .where(Configuration.workspace_id == workspace_id)
            .order_by(Configuration.created_at.asc())
        )
        result = self._session.execute(stmt)
        return result.scalars().all()

    def list_family_candidates(self, workspace_id: UUID) -> Sequence[Configuration]:
        """Return all configurations in a workspace for lineage graph traversal."""
        stmt = self.base_query().where(Configuration.workspace_id == workspace_id)
        result = self._session.execute(stmt)
        return result.scalars().all()

    def get_by_id(self, configuration_id: UUID) -> Configuration | None:
        stmt = self.base_query().where(Configuration.id == configuration_id).limit(1)
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_active(self, workspace_id: UUID) -> Configuration | None:
        stmt = (
            self
            .base_query()
            .where(
                Configuration.workspace_id == workspace_id,
                Configuration.status == ConfigurationStatus.ACTIVE,
            )
            .limit(1)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["ConfigurationsRepository"]
