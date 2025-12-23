"""Persistence helpers for ADE run metadata."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.pagination import Page, paginate_sql
from ade_api.models import Build, BuildStatus, Run, RunStatus

__all__ = ["RunsRepository"]


class RunsRepository:
    """Encapsulate read/write operations for runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, run_id: UUID) -> Run | None:
        """Return the ``Run`` identified by ``run_id`` if it exists."""

        return await self._session.get(Run, run_id)

    async def list_by_workspace(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID | None,
        statuses: Sequence[RunStatus] | None,
        input_document_id: UUID | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[Run]:
        """Return paginated runs for ``workspace_id`` filtered by config, status, or document."""

        stmt: Select = select(Run).where(Run.workspace_id == workspace_id)
        if configuration_id:
            stmt = stmt.where(Run.configuration_id == configuration_id)
        if statuses:
            stmt = stmt.where(Run.status.in_(statuses))
        if input_document_id:
            stmt = stmt.where(Run.input_document_id == input_document_id)

        return await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            include_total=include_total,
            order_by=[desc(Run.created_at)],
        )

    async def count_queued(self) -> int:
        stmt = select(func.count()).select_from(Run).where(Run.status == RunStatus.QUEUED)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def next_queued_with_terminal_build(self) -> tuple[Run, BuildStatus] | None:
        stmt = (
            select(Run, Build.status)
            .join(Build, Run.build_id == Build.id)
            .where(
                Run.status == RunStatus.QUEUED,
                Build.status.in_(
                    [
                        BuildStatus.READY,
                        BuildStatus.FAILED,
                        BuildStatus.CANCELLED,
                    ]
                ),
            )
            .order_by(Run.created_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        run, build_status = row
        return run, BuildStatus(build_status)
