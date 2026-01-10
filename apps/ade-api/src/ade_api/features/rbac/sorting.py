from __future__ import annotations

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

ROLE_SORT_FIELDS = {
    "name": lambda role: role.name.lower(),
    "slug": lambda role: role.slug.lower(),
    "createdAt": lambda role: role.created_at,
    "updatedAt": lambda role: role.updated_at or role.created_at,
    "isSystem": lambda role: role.is_system,
    "isEditable": lambda role: role.is_editable,
}
ROLE_DEFAULT_SORT = ["name"]


def role_id_key(role: Role) -> str:
    return str(role.id)


__all__ = [
    "ASSIGNMENT_DEFAULT_SORT",
    "ASSIGNMENT_ID_FIELD",
    "ASSIGNMENT_SORT_FIELDS",
    "PERMISSION_DEFAULT_SORT",
    "PERMISSION_ID_FIELD",
    "PERMISSION_SORT_FIELDS",
    "ROLE_DEFAULT_SORT",
    "ROLE_SORT_FIELDS",
    "role_id_key",
]
