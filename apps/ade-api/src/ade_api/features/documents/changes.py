"""Document change feed helpers (numeric cursor + delta queries)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

DOCUMENT_CHANGES_CHANNEL = "ade_document_changes"
DOCUMENT_CHANGES_TABLE = "document_changes"
DEFAULT_DELTA_LIMIT = 500
MAX_DELTA_LIMIT = 2000


@dataclass(frozen=True, slots=True)
class DocumentChangeRow:
    id: int
    document_id: UUID
    op: str


@dataclass(frozen=True, slots=True)
class DocumentChangeDelta:
    changes: list[DocumentChangeRow]
    next_since: int
    has_more: bool


def parse_document_change_cursor(token: str) -> int:
    """Parse a numeric change cursor from a query/Last-Event-ID value."""

    try:
        value = int(token)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Invalid change cursor.",
        ) from exc
    if value < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid change cursor.")
    return value


def get_latest_document_change_id(session: Session, workspace_id: UUID) -> int | None:
    row = session.execute(
        text(
            """
            SELECT id
            FROM document_changes
            WHERE workspace_id = :workspace_id
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"workspace_id": workspace_id},
    ).one_or_none()
    if row is None:
        return None
    return int(row[0])


def _get_earliest_document_change_id(session: Session, workspace_id: UUID) -> int | None:
    row = session.execute(
        text(
            """
            SELECT id
            FROM document_changes
            WHERE workspace_id = :workspace_id
            ORDER BY id ASC
            LIMIT 1
            """
        ),
        {"workspace_id": workspace_id},
    ).one_or_none()
    if row is None:
        return None
    return int(row[0])


def _coerce_delta_limit(limit: int | None) -> int:
    value = DEFAULT_DELTA_LIMIT if limit is None else int(limit)
    return max(1, min(value, MAX_DELTA_LIMIT))


def fetch_document_change_delta(
    session: Session,
    *,
    workspace_id: UUID,
    since: int,
    limit: int | None = None,
) -> DocumentChangeDelta:
    """Return ordered change rows since ``since``."""

    limit_value = _coerce_delta_limit(limit)
    earliest = _get_earliest_document_change_id(session, workspace_id)
    if earliest is not None and since < earliest:
        logger.info(
            "documents.changes.token_expired",
            extra={"workspace_id": str(workspace_id)},
        )
        raise HTTPException(
            status.HTTP_410_GONE,
            detail="Change cursor expired; refresh the document list.",
        )

    rows = session.execute(
        text(
            """
            SELECT id, document_id, op
            FROM document_changes
            WHERE workspace_id = :workspace_id
              AND id > :since_id
            ORDER BY id ASC
            LIMIT :limit_plus
            """
        ),
        {
            "workspace_id": workspace_id,
            "since_id": since,
            "limit_plus": limit_value + 1,
        },
    ).all()

    has_more = len(rows) > limit_value
    trimmed = rows[:limit_value]
    changes = [
        DocumentChangeRow(
            id=int(row.id),
            document_id=row.document_id,
            op=row.op,
        )
        for row in trimmed
    ]
    if changes:
        last = changes[-1]
        next_since = last.id
    else:
        next_since = since

    return DocumentChangeDelta(changes=changes, next_since=next_since, has_more=has_more)


def purge_document_changes(
    session: Session,
    *,
    retention_days: int,
) -> int:
    """Delete change rows outside the retention window."""

    retention_days = max(1, int(retention_days))
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = session.execute(
        text("DELETE FROM document_changes WHERE changed_at < :cutoff"),
        {"cutoff": cutoff},
    )
    return int(result.rowcount or 0)


def iter_document_change_ids(changes: Iterable[DocumentChangeRow]) -> list[int]:
    return [change.id for change in changes]


__all__ = [
    "DOCUMENT_CHANGES_CHANNEL",
    "DEFAULT_DELTA_LIMIT",
    "MAX_DELTA_LIMIT",
    "DocumentChangeDelta",
    "DocumentChangeRow",
    "parse_document_change_cursor",
    "fetch_document_change_delta",
    "get_latest_document_change_id",
    "purge_document_changes",
]
logger = logging.getLogger(__name__)
