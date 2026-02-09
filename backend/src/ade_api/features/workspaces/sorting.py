from __future__ import annotations

from ade_api.common.cursor_listing import (
    CursorFieldSpec,
    cursor_field,
    parse_bool,
    parse_datetime,
    parse_str,
    parse_uuid,
)

from .schemas import WorkspaceMemberOut, WorkspaceOut


def _lower(value: str | None) -> str:
    return (value or "").lower()


DEFAULT_SORT = ["name"]

MEMBER_DEFAULT_SORT = ["userId"]


WORKSPACE_CURSOR_FIELDS: dict[str, CursorFieldSpec[WorkspaceOut]] = {
    "id": cursor_field(lambda item: item.id, parse_uuid),
    "name": cursor_field(lambda item: _lower(item.name), parse_str),
    "slug": cursor_field(lambda item: _lower(item.slug), parse_str),
    "isDefault": cursor_field(lambda item: item.is_default, parse_bool),
    "processingPaused": cursor_field(lambda item: item.processing_paused, parse_bool),
}

MEMBER_CURSOR_FIELDS: dict[str, CursorFieldSpec[WorkspaceMemberOut]] = {
    "id": cursor_field(lambda item: item.user_id, parse_uuid),
    "userId": cursor_field(lambda item: item.user_id, parse_uuid),
    "createdAt": cursor_field(lambda item: item.created_at, parse_datetime),
}


__all__ = [
    "DEFAULT_SORT",
    "MEMBER_DEFAULT_SORT",
    "MEMBER_CURSOR_FIELDS",
    "WORKSPACE_CURSOR_FIELDS",
]
