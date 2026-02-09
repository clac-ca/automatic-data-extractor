from __future__ import annotations

from ade_api.common.cursor_listing import (
    CursorFieldSpec,
    cursor_field,
    cursor_field_nulls_last,
    parse_datetime,
    parse_enum,
    parse_uuid,
)
from ade_api.common.sql import nulls_last
from ade_api.models import Run, RunStatus

SORT_FIELDS = {
    "id": (Run.id.asc(), Run.id.desc()),
    "createdAt": (Run.created_at.asc(), Run.created_at.desc()),
    "startedAt": (
        tuple(nulls_last(Run.started_at.asc())),
        tuple(nulls_last(Run.started_at.desc())),
    ),
    "completedAt": (
        tuple(nulls_last(Run.completed_at.asc())),
        tuple(nulls_last(Run.completed_at.desc())),
    ),
    "status": (Run.status.asc(), Run.status.desc()),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (Run.id.asc(), Run.id.desc())

CURSOR_FIELDS: dict[str, CursorFieldSpec[Run]] = {
    "id": cursor_field(lambda run: run.id, parse_uuid),
    "createdAt": cursor_field(lambda run: run.created_at, parse_datetime),
    "startedAt": cursor_field_nulls_last(lambda run: run.started_at, parse_datetime),
    "completedAt": cursor_field_nulls_last(lambda run: run.completed_at, parse_datetime),
    "status": cursor_field(lambda run: run.status, parse_enum(RunStatus)),
}

__all__ = ["CURSOR_FIELDS", "DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
