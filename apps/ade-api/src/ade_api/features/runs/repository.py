"""Persistence helpers for ADE run metadata."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.runs.models import RunStatus
from ade_api.shared.pagination import Page, paginate_sql

from .models import Run, RunLog

__all__ = ["RunsRepository"]


class RunsRepository:
    """Encapsulate read/write operations for runs and associated logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, run_id: str) -> Run | None:
        """Return the ``Run`` identified by ``run_id`` if it exists."""

        return await self._session.get(Run, run_id)

    def logs_query(self) -> Select[tuple[RunLog]]:
        """Return a base selectable for run log records."""

        return select(RunLog)

    async def list_logs(
        self,
        *,
        run_id: str,
        after_id: int | None = None,
        limit: int = 1000,
    ) -> Sequence[RunLog]:
        """Fetch log rows for ``run_id`` ordered by creation ascending."""

        stmt = self.logs_query().where(RunLog.run_id == run_id)
        if after_id is not None:
            stmt = stmt.where(RunLog.id > after_id)
        stmt = stmt.order_by(RunLog.id.asc()).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_workspace(
        self,
        *,
        workspace_id: str,
        statuses: Sequence[RunStatus] | None,
        input_document_id: str | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[Run]:
        """Return paginated runs for ``workspace_id`` filtered by status or document."""

        stmt: Select = select(Run).where(Run.workspace_id == workspace_id)
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
