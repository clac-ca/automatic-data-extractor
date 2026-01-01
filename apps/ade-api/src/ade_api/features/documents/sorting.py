from __future__ import annotations

from sqlalchemy import case, func

from ade_api.common.sql import nulls_last
from ade_api.models import Document


def _activity_at_expr():
    return case(
        (Document.last_run_at.is_(None), Document.updated_at),
        (Document.updated_at.is_(None), Document.last_run_at),
        (Document.last_run_at > Document.updated_at, Document.last_run_at),
        else_=Document.updated_at,
    )


SORT_FIELDS = {
    "id": (Document.id.asc(), Document.id.desc()),
    "createdAt": (Document.created_at.asc(), Document.created_at.desc()),
    "updatedAt": (Document.updated_at.asc(), Document.updated_at.desc()),
    "status": (Document.status.asc(), Document.status.desc()),
    "latestRunAt": (
        tuple(nulls_last(Document.last_run_at.asc())),
        tuple(nulls_last(Document.last_run_at.desc())),
    ),
    "activityAt": (
        tuple(nulls_last(_activity_at_expr().asc())),
        tuple(nulls_last(_activity_at_expr().desc())),
    ),
    "byteSize": (Document.byte_size.asc(), Document.byte_size.desc()),
    "source": (Document.source.asc(), Document.source.desc()),
    "name": (
        func.lower(Document.original_filename).asc(),
        func.lower(Document.original_filename).desc(),
    ),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (Document.id.asc(), Document.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
