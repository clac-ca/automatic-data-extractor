from __future__ import annotations

from sqlalchemy import func

from ade_api.common.cursor_listing import (
    CursorFieldSpec,
    cursor_field,
    cursor_field_nulls_last,
    parse_datetime,
    parse_str,
    parse_uuid,
)
from ade_api.common.sql import nulls_last
from ade_db.models import Invitation

SORT_FIELDS = {
    "id": (Invitation.id.asc(), Invitation.id.desc()),
    "createdAt": (Invitation.created_at.asc(), Invitation.created_at.desc()),
    "expiresAt": (
        tuple(nulls_last(Invitation.expires_at.asc())),
        tuple(nulls_last(Invitation.expires_at.desc())),
    ),
    "email": (
        tuple(nulls_last(func.lower(Invitation.email_normalized).asc())),
        tuple(nulls_last(func.lower(Invitation.email_normalized).desc())),
    ),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (Invitation.id.asc(), Invitation.id.desc())

CURSOR_FIELDS: dict[str, CursorFieldSpec[Invitation]] = {
    "id": cursor_field(lambda invitation: invitation.id, parse_uuid),
    "createdAt": cursor_field(lambda invitation: invitation.created_at, parse_datetime),
    "expiresAt": cursor_field_nulls_last(lambda invitation: invitation.expires_at, parse_datetime),
    "email": cursor_field(lambda invitation: invitation.email_normalized.lower(), parse_str),
}

__all__ = ["CURSOR_FIELDS", "DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]

