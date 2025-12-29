from __future__ import annotations

from ade_api.common.sql import nulls_last
from ade_api.models import Run

SORT_FIELDS = {
    "id": (Run.id.asc(), Run.id.desc()),
    "created_at": (Run.created_at.asc(), Run.created_at.desc()),
    "started_at": (
        tuple(nulls_last(Run.started_at.asc())),
        tuple(nulls_last(Run.started_at.desc())),
    ),
    "completed_at": (
        tuple(nulls_last(Run.completed_at.asc())),
        tuple(nulls_last(Run.completed_at.desc())),
    ),
    "status": (Run.status.asc(), Run.status.desc()),
}

DEFAULT_SORT = ["-created_at"]
ID_FIELD = (Run.id.asc(), Run.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
