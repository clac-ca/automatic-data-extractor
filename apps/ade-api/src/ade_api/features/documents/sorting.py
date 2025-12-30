from __future__ import annotations

from sqlalchemy import case, func

from ade_api.common.sql import nulls_last
from ade_api.models import Document, DocumentStatus


def _activity_at_expr():
    return case(
        (Document.last_run_at.is_(None), Document.updated_at),
        (Document.updated_at.is_(None), Document.last_run_at),
        (Document.last_run_at > Document.updated_at, Document.last_run_at),
        else_=Document.updated_at,
    )


def _display_status_rank():
    return case(
        (Document.status == DocumentStatus.UPLOADED, 0),
        (Document.status == DocumentStatus.PROCESSING, 1),
        (Document.status == DocumentStatus.PROCESSED, 2),
        (Document.status == DocumentStatus.FAILED, 3),
        (Document.status == DocumentStatus.ARCHIVED, 4),
        else_=0,
    )

SORT_FIELDS = {
    "id": (Document.id.asc(), Document.id.desc()),
    "created_at": (Document.created_at.asc(), Document.created_at.desc()),
    "status": (Document.status.asc(), Document.status.desc()),
    "display_status": (_display_status_rank().asc(), _display_status_rank().desc()),
    "last_run_at": (
        tuple(nulls_last(Document.last_run_at.asc())),
        tuple(nulls_last(Document.last_run_at.desc())),
    ),
    "activity_at": (
        tuple(nulls_last(_activity_at_expr().asc())),
        tuple(nulls_last(_activity_at_expr().desc())),
    ),
    "byte_size": (Document.byte_size.asc(), Document.byte_size.desc()),
    "source": (Document.source.asc(), Document.source.desc()),
    "name": (
        func.lower(Document.original_filename).asc(),
        func.lower(Document.original_filename).desc(),
    ),
}

DEFAULT_SORT = ["-created_at"]
ID_FIELD = (Document.id.asc(), Document.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
