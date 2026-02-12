from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func

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
from ade_db.models import (
    AssignmentScopeType,
    Permission,
    PrincipalType,
    Role,
    RoleAssignment,
    UserRoleAssignment,
)


@dataclass(frozen=True)
class PrincipalAssignmentRow:
    id: UUID
    principal_type: PrincipalType
    principal_id: UUID
    role_id: UUID
    role_slug: str
    scope_type: AssignmentScopeType
    scope_id: UUID | None
    created_at: datetime
    principal_display_name: str | None
    principal_email: str | None
    principal_slug: str | None

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

PRINCIPAL_ASSIGNMENT_SORT_FIELDS = {
    "id": (RoleAssignment.id.asc(), RoleAssignment.id.desc()),
    "createdAt": (RoleAssignment.created_at.asc(), RoleAssignment.created_at.desc()),
    "principalType": (RoleAssignment.principal_type.asc(), RoleAssignment.principal_type.desc()),
    "principalId": (RoleAssignment.principal_id.asc(), RoleAssignment.principal_id.desc()),
    "roleId": (RoleAssignment.role_id.asc(), RoleAssignment.role_id.desc()),
    "scopeType": (RoleAssignment.scope_type.asc(), RoleAssignment.scope_type.desc()),
    "scopeId": (
        tuple(nulls_last(RoleAssignment.scope_id.asc())),
        tuple(nulls_last(RoleAssignment.scope_id.desc())),
    ),
}
PRINCIPAL_ASSIGNMENT_DEFAULT_SORT = ["-createdAt"]
PRINCIPAL_ASSIGNMENT_ID_FIELD = (RoleAssignment.id.asc(), RoleAssignment.id.desc())

ROLE_DEFAULT_SORT = ["name"]
ROLE_SORT_FIELDS = {
    "id": (Role.id.asc(), Role.id.desc()),
    "name": (func.lower(Role.name).asc(), func.lower(Role.name).desc()),
    "slug": (func.lower(Role.slug).asc(), func.lower(Role.slug).desc()),
    "createdAt": (Role.created_at.asc(), Role.created_at.desc()),
    "updatedAt": (
        func.coalesce(Role.updated_at, Role.created_at).asc(),
        func.coalesce(Role.updated_at, Role.created_at).desc(),
    ),
    "isSystem": (Role.is_system.asc(), Role.is_system.desc()),
    "isEditable": (Role.is_editable.asc(), Role.is_editable.desc()),
}
ROLE_ID_FIELD = (Role.id.asc(), Role.id.desc())


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

PRINCIPAL_ASSIGNMENT_CURSOR_FIELDS: dict[str, CursorFieldSpec[PrincipalAssignmentRow]] = {
    "id": cursor_field(lambda item: item.id, parse_uuid),
    "createdAt": cursor_field(lambda item: item.created_at, parse_datetime),
    "principalType": cursor_field(lambda item: item.principal_type.value, parse_str),
    "principalId": cursor_field(lambda item: item.principal_id, parse_uuid),
    "roleId": cursor_field(lambda item: item.role_id, parse_uuid),
    "scopeType": cursor_field(lambda item: item.scope_type.value, parse_str),
    "scopeId": cursor_field_nulls_last(lambda item: item.scope_id, parse_uuid),
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
    "PRINCIPAL_ASSIGNMENT_DEFAULT_SORT",
    "PRINCIPAL_ASSIGNMENT_ID_FIELD",
    "PRINCIPAL_ASSIGNMENT_CURSOR_FIELDS",
    "PRINCIPAL_ASSIGNMENT_SORT_FIELDS",
    "PrincipalAssignmentRow",
    "PERMISSION_DEFAULT_SORT",
    "PERMISSION_CURSOR_FIELDS",
    "PERMISSION_ID_FIELD",
    "PERMISSION_SORT_FIELDS",
    "ROLE_DEFAULT_SORT",
    "ROLE_CURSOR_FIELDS",
    "ROLE_ID_FIELD",
    "ROLE_SORT_FIELDS",
]
