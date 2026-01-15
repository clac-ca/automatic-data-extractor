from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func

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
from ade_api.models import Document, DocumentComment, DocumentSource


def _activity_at_expr():
    return case(
        (Document.last_run_at.is_(None), Document.updated_at),
        (Document.updated_at.is_(None), Document.last_run_at),
        (Document.last_run_at > Document.updated_at, Document.last_run_at),
        else_=Document.updated_at,
    )

def _activity_at_value(document: Document) -> datetime | None:
    if document.last_run_at is None:
        return document.updated_at
    if document.updated_at is None:
        return document.last_run_at
    return document.last_run_at if document.last_run_at > document.updated_at else document.updated_at


SORT_FIELDS = {
    "id": (Document.id.asc(), Document.id.desc()),
    "createdAt": (Document.created_at.asc(), Document.created_at.desc()),
    "updatedAt": (Document.updated_at.asc(), Document.updated_at.desc()),
    "lastRunAt": (
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

CURSOR_FIELDS: dict[str, CursorFieldSpec[Document]] = {
    "id": cursor_field(lambda doc: doc.id, parse_uuid),
    "createdAt": cursor_field(lambda doc: doc.created_at, parse_datetime),
    "updatedAt": cursor_field(lambda doc: doc.updated_at, parse_datetime),
    "lastRunAt": cursor_field_nulls_last(lambda doc: doc.last_run_at, parse_datetime),
    "activityAt": cursor_field_nulls_last(_activity_at_value, parse_datetime),
    "byteSize": cursor_field(lambda doc: doc.byte_size, parse_int),
    "source": cursor_field(lambda doc: doc.source, parse_enum(DocumentSource)),
    "name": cursor_field(lambda doc: (doc.original_filename or "").lower(), parse_str),
}

__all__ = ["CURSOR_FIELDS", "DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]


COMMENT_SORT_FIELDS = {
    "id": (DocumentComment.id.asc(), DocumentComment.id.desc()),
    "createdAt": (DocumentComment.created_at.asc(), DocumentComment.created_at.desc()),
}

COMMENT_DEFAULT_SORT = ["createdAt"]
COMMENT_ID_FIELD = (DocumentComment.id.asc(), DocumentComment.id.desc())

COMMENT_CURSOR_FIELDS: dict[str, CursorFieldSpec[DocumentComment]] = {
    "id": cursor_field(lambda comment: comment.id, parse_uuid),
    "createdAt": cursor_field(lambda comment: comment.created_at, parse_datetime),
}

__all__ += [
    "COMMENT_CURSOR_FIELDS",
    "COMMENT_DEFAULT_SORT",
    "COMMENT_ID_FIELD",
    "COMMENT_SORT_FIELDS",
]
