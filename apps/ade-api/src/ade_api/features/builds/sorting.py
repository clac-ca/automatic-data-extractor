from __future__ import annotations

from ade_api.common.sql import nulls_last
from ade_api.models import Build

SORT_FIELDS = {
    "id": (Build.id.asc(), Build.id.desc()),
    "createdAt": (Build.created_at.asc(), Build.created_at.desc()),
    "startedAt": (
        tuple(nulls_last(Build.started_at.asc())),
        tuple(nulls_last(Build.started_at.desc())),
    ),
    "finishedAt": (
        tuple(nulls_last(Build.finished_at.asc())),
        tuple(nulls_last(Build.finished_at.desc())),
    ),
    "status": (Build.status.asc(), Build.status.desc()),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (Build.id.asc(), Build.id.desc())

__all__ = ["DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
