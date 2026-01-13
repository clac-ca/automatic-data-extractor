"""Persistence helpers for ADE run metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ade_api.common.cursor_listing import ResolvedCursorSort, paginate_query_cursor
from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.models import Run, RunField, RunMetrics, RunStatus, RunTableColumn

from .filters import RunColumnFilters, apply_run_column_filters, apply_run_filters

__all__ = ["RunsRepository"]


class RunsRepository:
    """Encapsulate read/write operations for runs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, run_id: UUID) -> Run | None:
        """Return the ``Run`` identified by ``run_id`` if it exists."""

        return self._session.get(Run, run_id)

    def list_by_workspace(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID | None,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        resolved_sort: ResolvedCursorSort[Run],
        limit: int,
        cursor: str | None,
        include_total: bool,
    ):
        """Return paginated runs for ``workspace_id`` filtered by config, status, or document."""

        stmt: Select = select(Run).where(Run.workspace_id == workspace_id)
        if configuration_id:
            stmt = stmt.where(Run.configuration_id == configuration_id)
        stmt = apply_run_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )

        return paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )

    def count_queued(self) -> int:
        stmt = (
            select(func.count())
            .select_from(Run)
            .where(
                Run.status == RunStatus.QUEUED,
                Run.attempt_count < Run.max_attempts,
            )
        )
        result = self._session.execute(stmt)
        return int(result.scalar_one())

    def list_active_for_documents(
        self,
        *,
        configuration_id: UUID,
        document_ids: list[UUID],
    ) -> list[Run]:
        if not document_ids:
            return []
        stmt = select(Run).where(
            Run.configuration_id == configuration_id,
            Run.input_document_id.in_(document_ids),
            Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def get_metrics(self, run_id: UUID) -> RunMetrics | None:
        return self._session.get(RunMetrics, run_id)

    def list_fields(self, run_id: UUID) -> list[RunField]:
        stmt = (
            select(RunField)
            .where(RunField.run_id == run_id)
            .order_by(RunField.field.asc())
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def list_columns(
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
        result = self._session.execute(stmt)
        return list(result.scalars().all())
