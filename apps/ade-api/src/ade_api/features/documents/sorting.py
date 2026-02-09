from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select

from ade_api.common.cursor_listing import (
    CursorFieldSpec,
    cursor_field,
    cursor_field_nulls_last,
    parse_datetime,
    parse_enum,
    parse_int,
    parse_str,
    parse_uuid,
)
from ade_api.common.sql import nulls_last
from ade_api.models import File, FileComment, FileVersion, FileVersionOrigin, Run


def _current_version_byte_size_expr():
    return (
        select(FileVersion.byte_size)
        .where(FileVersion.id == File.current_version_id)
        .scalar_subquery()
    )


def _current_version_origin_expr():
    return (
        select(FileVersion.origin)
        .where(FileVersion.id == File.current_version_id)
        .scalar_subquery()
    )


def _last_run_at_expr():
    return (
        select(func.max(func.coalesce(Run.completed_at, Run.started_at, Run.created_at)))
        .select_from(Run)
        .join(FileVersion, Run.input_file_version_id == FileVersion.id)
        .where(
            FileVersion.file_id == File.id,
            Run.workspace_id == File.workspace_id,
        )
        .scalar_subquery()
    )


def _activity_at_expr():
    last_run_at = _last_run_at_expr()
    return case(
        (last_run_at.is_(None), File.updated_at),
        (File.updated_at.is_(None), last_run_at),
        (last_run_at > File.updated_at, last_run_at),
        else_=File.updated_at,
    )


def _activity_at_value(document: File) -> datetime | None:
    last_run_at = getattr(document, "_last_run_at", None)
    if last_run_at is None:
        return document.updated_at
    if document.updated_at is None:
        return last_run_at
    return last_run_at if last_run_at > document.updated_at else document.updated_at


SORT_FIELDS = {
    "id": (File.id.asc(), File.id.desc()),
    "createdAt": (File.created_at.asc(), File.created_at.desc()),
    "updatedAt": (File.updated_at.asc(), File.updated_at.desc()),
    "lastRunAt": (
        tuple(nulls_last(_last_run_at_expr().asc())),
        tuple(nulls_last(_last_run_at_expr().desc())),
    ),
    "activityAt": (
        tuple(nulls_last(_activity_at_expr().asc())),
        tuple(nulls_last(_activity_at_expr().desc())),
    ),
    "byteSize": (_current_version_byte_size_expr().asc(), _current_version_byte_size_expr().desc()),
    "source": (_current_version_origin_expr().asc(), _current_version_origin_expr().desc()),
    "name": (
        func.lower(File.name).asc(),
        func.lower(File.name).desc(),
    ),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (File.id.asc(), File.id.desc())

CURSOR_FIELDS: dict[str, CursorFieldSpec[File]] = {
    "id": cursor_field(lambda doc: doc.id, parse_uuid),
    "createdAt": cursor_field(lambda doc: doc.created_at, parse_datetime),
    "updatedAt": cursor_field(lambda doc: doc.updated_at, parse_datetime),
    "lastRunAt": cursor_field_nulls_last(
        lambda doc: getattr(doc, "_last_run_at", None),
        parse_datetime,
    ),
    "activityAt": cursor_field_nulls_last(_activity_at_value, parse_datetime),
    "byteSize": cursor_field(lambda doc: doc.byte_size, parse_int),
    "source": cursor_field(lambda doc: doc.source, parse_enum(FileVersionOrigin)),
    "name": cursor_field(lambda doc: (doc.name or "").lower(), parse_str),
}

__all__ = ["CURSOR_FIELDS", "DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]


COMMENT_SORT_FIELDS = {
    "id": (FileComment.id.asc(), FileComment.id.desc()),
    "createdAt": (FileComment.created_at.asc(), FileComment.created_at.desc()),
}

COMMENT_DEFAULT_SORT = ["createdAt"]
COMMENT_ID_FIELD = (FileComment.id.asc(), FileComment.id.desc())

COMMENT_CURSOR_FIELDS: dict[str, CursorFieldSpec[FileComment]] = {
    "id": cursor_field(lambda comment: comment.id, parse_uuid),
    "createdAt": cursor_field(lambda comment: comment.created_at, parse_datetime),
}

__all__ += [
    "COMMENT_CURSOR_FIELDS",
    "COMMENT_DEFAULT_SORT",
    "COMMENT_ID_FIELD",
    "COMMENT_SORT_FIELDS",
]
