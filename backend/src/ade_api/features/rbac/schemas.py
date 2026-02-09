from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ade_api.common.cursor_listing import CursorPage
from ade_api.common.schema import BaseSchema
from ade_api.core.rbac.types import ScopeType


class PermissionOut(BaseSchema):
    """API representation of a permission from the catalog."""

    id: UUID
    key: str
    resource: str
    action: str
    scope_type: ScopeType
    label: str
    description: str


class RoleCreate(BaseSchema):
    """Payload for creating a new role."""

    name: str
    slug: str | None = None
    description: str | None = None
    permissions: list[str]


class RoleUpdate(BaseSchema):
    """Payload for updating an existing role."""

    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class RoleOut(BaseSchema):
    """API representation of a role."""

    id: UUID
    slug: str
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool
    is_editable: bool
    created_at: datetime
    updated_at: datetime | None


class RoleAssignmentOut(BaseSchema):
    """API representation of a role assignment to a user in a scope."""

    id: UUID
    user_id: UUID
    role_id: UUID
    role_slug: str
    scope_type: ScopeType
    scope_id: UUID | None
    created_at: datetime


class RolePage(CursorPage[RoleOut]):
    """Cursor-based role collection."""


class RoleAssignmentPage(CursorPage[RoleAssignmentOut]):
    """Cursor-based role assignment collection."""


class PermissionPage(CursorPage[PermissionOut]):
    """Cursor-based permission registry response."""


class UserRoleSummary(BaseSchema):
    """Summary of a single role assignment for a user (global scope)."""

    role_id: UUID
    role_slug: str
    created_at: datetime


class UserRolesEnvelope(BaseSchema):
    """Envelope for listing all global roles for a user."""

    user_id: UUID
    roles: list[UserRoleSummary]


class WorkspaceMemberOut(BaseSchema):
    """Workspace member representation with assigned roles."""

    user_id: UUID
    role_ids: list[UUID]
    role_slugs: list[str]
    created_at: datetime
