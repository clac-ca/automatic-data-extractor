from __future__ import annotations

from sqlalchemy import func

from ade_api.common.cursor_listing import (
    CursorFieldSpec,
    cursor_field,
    cursor_field_nulls_last,
    parse_bool,
    parse_datetime,
    parse_int,
    parse_str,
    parse_uuid,
)
from ade_api.common.sql import nulls_last
from ade_db.models import User

SORT_FIELDS = {
    "id": (User.id.asc(), User.id.desc()),
    "email": (
        func.lower(User.email).asc(),
        func.lower(User.email).desc(),
    ),
    "displayName": (
        tuple(nulls_last(func.lower(User.display_name).asc())),
        tuple(nulls_last(func.lower(User.display_name).desc())),
    ),
    "createdAt": (User.created_at.asc(), User.created_at.desc()),
    "updatedAt": (User.updated_at.asc(), User.updated_at.desc()),
    "lastLoginAt": (
        tuple(nulls_last(User.last_login_at.asc())),
        tuple(nulls_last(User.last_login_at.desc())),
    ),
    "failedLoginCount": (User.failed_login_count.asc(), User.failed_login_count.desc()),
    "isActive": (User.is_active.asc(), User.is_active.desc()),
    "isServiceAccount": (
        User.is_service_account.asc(),
        User.is_service_account.desc(),
    ),
}

DEFAULT_SORT = ["email"]
ID_FIELD = (User.id.asc(), User.id.desc())

CURSOR_FIELDS: dict[str, CursorFieldSpec[User]] = {
    "id": cursor_field(lambda user: user.id, parse_uuid),
    "email": cursor_field(lambda user: user.email.lower(), parse_str),
    "displayName": cursor_field_nulls_last(
        lambda user: (user.display_name or "").lower(), parse_str
    ),
    "createdAt": cursor_field(lambda user: user.created_at, parse_datetime),
    "updatedAt": cursor_field(lambda user: user.updated_at, parse_datetime),
    "lastLoginAt": cursor_field_nulls_last(lambda user: user.last_login_at, parse_datetime),
    "failedLoginCount": cursor_field(lambda user: user.failed_login_count, parse_int),
    "isActive": cursor_field(lambda user: user.is_active, parse_bool),
    "isServiceAccount": cursor_field(lambda user: user.is_service_account, parse_bool),
}

__all__ = ["CURSOR_FIELDS", "DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
