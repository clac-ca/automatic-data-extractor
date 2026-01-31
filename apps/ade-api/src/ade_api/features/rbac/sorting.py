from __future__ import annotations

from ade_api.common.cursor_listing import (
    CursorFieldSpec,
    cursor_field,
    cursor_field_nulls_last,
    parse_bool,
    parse_datetime,
    parse_str,
    parse_uuid,
)
from ade_api.common.sql import nulls_last
from ade_api.models import Permission, Role, UserRoleAssignment

PERMISSION_SORT_FIELDS = {
    "id": (Permission.id.asc(), Permission.id.desc()),
    "key": (Permission.key.asc(), Permission.key.desc()),
    "resource": (Permission.resource.asc(), Permission.resource.desc()),
    "action": (Permission.action.asc(), Permission.action.desc()),
    "label": (Permission.label.asc(), Permission.label.desc()),
    "scopeType": (Permission.scope_type.asc(), Permission.scope_type.desc()),
}
PERMISSION_DEFAULT_SORT = ["key"]
PERMISSION_ID_FIELD = (Permission.id.asc(), Permission.id.desc())

ASSIGNMENT_SORT_FIELDS = {
    "id": (UserRoleAssignment.id.asc(), UserRoleAssignment.id.desc()),
    "createdAt": (UserRoleAssignment.created_at.asc(), UserRoleAssignment.created_at.desc()),
    "userId": (UserRoleAssignment.user_id.asc(), UserRoleAssignment.user_id.desc()),
    "roleId": (UserRoleAssignment.role_id.asc(), UserRoleAssignment.role_id.desc()),
    "scopeId": (
        tuple(nulls_last(UserRoleAssignment.workspace_id.asc())),
        tuple(nulls_last(UserRoleAssignment.workspace_id.desc())),
    ),
}
ASSIGNMENT_DEFAULT_SORT = ["-createdAt"]
ASSIGNMENT_ID_FIELD = (UserRoleAssignment.id.asc(), UserRoleAssignment.id.desc())

ROLE_DEFAULT_SORT = ["name"]


PERMISSION_CURSOR_FIELDS: dict[str, CursorFieldSpec[Permission]] = {
    "id": cursor_field(lambda item: item.id, parse_uuid),
    "key": cursor_field(lambda item: item.key, parse_str),
    "resource": cursor_field(lambda item: item.resource, parse_str),
    "action": cursor_field(lambda item: item.action, parse_str),
    "label": cursor_field(lambda item: item.label, parse_str),
    "scopeType": cursor_field(lambda item: item.scope_type, parse_str),
}

ASSIGNMENT_CURSOR_FIELDS: dict[str, CursorFieldSpec[UserRoleAssignment]] = {
    "id": cursor_field(lambda item: item.id, parse_uuid),
    "createdAt": cursor_field(lambda item: item.created_at, parse_datetime),
    "userId": cursor_field(lambda item: item.user_id, parse_uuid),
    "roleId": cursor_field(lambda item: item.role_id, parse_uuid),
    "scopeId": cursor_field_nulls_last(lambda item: item.workspace_id, parse_uuid),
}

ROLE_CURSOR_FIELDS: dict[str, CursorFieldSpec[Role]] = {
    "id": cursor_field(lambda role: role.id, parse_uuid),
    "name": cursor_field(lambda role: role.name.lower(), parse_str),
    "slug": cursor_field(lambda role: role.slug.lower(), parse_str),
    "createdAt": cursor_field(lambda role: role.created_at, parse_datetime),
    "updatedAt": cursor_field(lambda role: role.updated_at or role.created_at, parse_datetime),
    "isSystem": cursor_field(lambda role: role.is_system, parse_bool),
    "isEditable": cursor_field(lambda role: role.is_editable, parse_bool),
}


__all__ = [
    "ASSIGNMENT_DEFAULT_SORT",
    "ASSIGNMENT_ID_FIELD",
    "ASSIGNMENT_CURSOR_FIELDS",
    "ASSIGNMENT_SORT_FIELDS",
    "PERMISSION_DEFAULT_SORT",
    "PERMISSION_CURSOR_FIELDS",
    "PERMISSION_ID_FIELD",
    "PERMISSION_SORT_FIELDS",
    "ROLE_DEFAULT_SORT",
    "ROLE_CURSOR_FIELDS",
]
