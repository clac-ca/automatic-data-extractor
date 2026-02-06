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
from ade_db.models import ApiKey

SORT_FIELDS = {
    "id": (ApiKey.id.asc(), ApiKey.id.desc()),
    "createdAt": (ApiKey.created_at.asc(), ApiKey.created_at.desc()),
    "expiresAt": (
        tuple(nulls_last(ApiKey.expires_at.asc())),
        tuple(nulls_last(ApiKey.expires_at.desc())),
    ),
    "revokedAt": (
        tuple(nulls_last(ApiKey.revoked_at.asc())),
        tuple(nulls_last(ApiKey.revoked_at.desc())),
    ),
    "lastUsedAt": (
        tuple(nulls_last(ApiKey.last_used_at.asc())),
        tuple(nulls_last(ApiKey.last_used_at.desc())),
    ),
    "name": (
        tuple(nulls_last(func.lower(ApiKey.name).asc())),
        tuple(nulls_last(func.lower(ApiKey.name).desc())),
    ),
    "prefix": (ApiKey.prefix.asc(), ApiKey.prefix.desc()),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (ApiKey.id.asc(), ApiKey.id.desc())

CURSOR_FIELDS: dict[str, CursorFieldSpec[ApiKey]] = {
    "id": cursor_field(lambda key: key.id, parse_uuid),
    "createdAt": cursor_field(lambda key: key.created_at, parse_datetime),
    "expiresAt": cursor_field_nulls_last(lambda key: key.expires_at, parse_datetime),
    "revokedAt": cursor_field_nulls_last(lambda key: key.revoked_at, parse_datetime),
    "lastUsedAt": cursor_field_nulls_last(lambda key: key.last_used_at, parse_datetime),
    "name": cursor_field_nulls_last(lambda key: (key.name or "").lower(), parse_str),
    "prefix": cursor_field(lambda key: key.prefix, parse_str),
}

__all__ = ["CURSOR_FIELDS", "DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
