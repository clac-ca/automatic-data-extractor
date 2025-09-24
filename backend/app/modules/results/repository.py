from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ExtractedTable


class ExtractedTablesRepository:
    """Persist and query extracted table artefacts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_job_tables(
        self,
        *,
        job_id: str,
        document_id: str,
        tables: Sequence[Mapping[str, Any]],
    ) -> list[ExtractedTable]:
        """Replace stored tables for ``job_id`` with ``tables``."""

        await self._session.execute(
            delete(ExtractedTable).where(ExtractedTable.job_id == job_id)
        )

        records: list[ExtractedTable] = []
        for index, payload in enumerate(tables):
            columns = list(payload.get("columns") or [])
            rows = list(payload.get("rows") or payload.get("sample_rows") or [])
            metadata = dict(payload.get("metadata") or {})

            sequence_index = _coerce_int(payload.get("sequence_index"), index)
            row_count = _coerce_int(payload.get("row_count"), len(rows))
            title = payload.get("title")
            title_value = str(title) if title is not None else None

            record = ExtractedTable(
                job_id=job_id,
                document_id=document_id,
                sequence_index=sequence_index,
                title=title_value,
                row_count=row_count,
                columns=[str(column) for column in columns],
                sample_rows=[dict(row) for row in rows],
                metadata_=metadata,
            )
            self._session.add(record)
            records.append(record)

        await self._session.flush()
        return records

    async def list_for_job(self, job_id: str) -> list[ExtractedTable]:
        """Return tables associated with ``job_id`` ordered by sequence."""

        statement = (
            select(ExtractedTable)
            .where(ExtractedTable.job_id == job_id)
            .order_by(ExtractedTable.sequence_index, ExtractedTable.created_at)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def list_for_document(self, document_id: str) -> list[ExtractedTable]:
        """Return tables associated with ``document_id`` ordered by sequence."""

        statement = (
            select(ExtractedTable)
            .where(ExtractedTable.document_id == document_id)
            .order_by(ExtractedTable.sequence_index, ExtractedTable.created_at)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_table(self, table_id: str) -> ExtractedTable | None:
        """Return a single table by identifier."""

        return await self._session.get(ExtractedTable, table_id)


def _coerce_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


__all__ = ["ExtractedTablesRepository"]
