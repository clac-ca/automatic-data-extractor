"""Persistence helpers for ADE run metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.pagination import Page, paginate_sql
from ade_api.common.types import OrderBy
from ade_api.models import (
    Build,
    BuildStatus,
    Run,
    RunField,
    RunMetrics,
    RunStatus,
    RunTableColumn,
)

from .filters import RunColumnFilters, RunFilters, apply_run_column_filters, apply_run_filters

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
        filters: RunFilters,
        order_by: OrderBy,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[Run]:
        """Return paginated runs for ``workspace_id`` filtered by config, status, or document."""

        stmt: Select = select(Run).where(Run.workspace_id == workspace_id)
        if configuration_id:
            stmt = stmt.where(Run.configuration_id == configuration_id)
        stmt = apply_run_filters(stmt, filters)

        return await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            include_total=include_total,
            order_by=order_by,
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

    async def get_metrics(self, run_id: UUID) -> RunMetrics | None:
        return await self._session.get(RunMetrics, run_id)

    async def list_fields(self, run_id: UUID) -> list[RunField]:
        stmt = (
            select(RunField)
            .where(RunField.run_id == run_id)
            .order_by(RunField.field.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_columns(
        self,
        *,
        run_id: UUID,
        filters: RunColumnFilters,
    ) -> list[RunTableColumn]:
        stmt: Select = select(RunTableColumn).where(RunTableColumn.run_id == run_id)
        stmt = apply_run_column_filters(stmt, filters)
        stmt = stmt.order_by(
            RunTableColumn.workbook_index.asc(),
            RunTableColumn.sheet_index.asc(),
            RunTableColumn.table_index.asc(),
            RunTableColumn.column_index.asc(),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
