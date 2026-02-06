from __future__ import annotations

from ade_api.common.cursor_listing import (
    CursorFieldSpec,
    cursor_field,
    cursor_field_nulls_last,
    parse_datetime,
    parse_enum,
    parse_str,
    parse_uuid,
)
from ade_api.common.sql import nulls_last
from ade_db.models import Configuration, ConfigurationStatus

SORT_FIELDS = {
    "id": (Configuration.id.asc(), Configuration.id.desc()),
    "displayName": (Configuration.display_name.asc(), Configuration.display_name.desc()),
    "status": (Configuration.status.asc(), Configuration.status.desc()),
    "createdAt": (Configuration.created_at.asc(), Configuration.created_at.desc()),
    "updatedAt": (Configuration.updated_at.asc(), Configuration.updated_at.desc()),
    "activatedAt": (
        tuple(nulls_last(Configuration.activated_at.asc())),
        tuple(nulls_last(Configuration.activated_at.desc())),
    ),
    "lastUsedAt": (
        tuple(nulls_last(Configuration.last_used_at.asc())),
        tuple(nulls_last(Configuration.last_used_at.desc())),
    ),
}

DEFAULT_SORT = ["-createdAt"]
ID_FIELD = (Configuration.id.asc(), Configuration.id.desc())

CURSOR_FIELDS: dict[str, CursorFieldSpec[Configuration]] = {
    "id": cursor_field(lambda config: config.id, parse_uuid),
    "displayName": cursor_field(lambda config: config.display_name, parse_str),
    "status": cursor_field(lambda config: config.status, parse_enum(ConfigurationStatus)),
    "createdAt": cursor_field(lambda config: config.created_at, parse_datetime),
    "updatedAt": cursor_field(lambda config: config.updated_at, parse_datetime),
    "activatedAt": cursor_field_nulls_last(lambda config: config.activated_at, parse_datetime),
    "lastUsedAt": cursor_field_nulls_last(lambda config: config.last_used_at, parse_datetime),
}

__all__ = ["CURSOR_FIELDS", "DEFAULT_SORT", "ID_FIELD", "SORT_FIELDS"]
