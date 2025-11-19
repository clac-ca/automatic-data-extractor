from __future__ import annotations

from sqlalchemy import func

from ade_api.shared.sql import nulls_last

from .models import Document

SORT_FIELDS = {
    "id": (Document.id.asc(), Document.id.desc()),
    "created_at": (Document.created_at.asc(), Document.created_at.desc()),
    "status": (Document.status.asc(), Document.status.desc()),
    "last_run_at": (
        nulls_last(Document.last_run_at.asc()),
        nulls_last(Document.last_run_at.desc()),
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
