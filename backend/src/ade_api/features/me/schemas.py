"""Schemas for the `/me` feature."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from ade_api.common.ids import UUIDStr
from ade_api.common.schema import BaseSchema


class MeProfile(BaseSchema):
    """Profile for the authenticated principal."""

    id: UUIDStr = Field(description="Unique user identifier.")
    email: EmailStr = Field(description="Primary email address.")
    display_name: str | None = Field(
        default=None,
        description="Human-friendly name for display.",
    )
    is_service_account: bool = Field(
        description="True when this principal is a service account.",
    )
    preferred_workspace_id: UUIDStr | None = Field(
        default=None,
        alias="preferred_workspace_id",
        description="Default workspace selection for this principal, when set.",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Global role slugs assigned to the principal.",
    )
    permissions: list[str] = Field(
        default_factory=list,
        description="Global permission keys granted to the principal.",
    )
    created_at: datetime = Field(description="User creation timestamp.")
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp of last profile update, if any.",
    )


class MeProfileUpdateRequest(BaseSchema):
    """Payload for updating editable fields on the caller profile."""

    display_name: str | None = Field(
        default=None,
        alias="display_name",
        description="Optional display name shown in the ADE user interface.",
    )


class MeWorkspaceSummary(BaseSchema):
    """Lightweight view of a workspace visible to the current principal."""

    id: UUIDStr = Field(description="Workspace identifier.")
    name: str = Field(description="Workspace display name.")
    slug: str | None = Field(
        default=None,
        description="Optional URL-friendly slug for the workspace.",
    )
    is_default: bool = Field(
        description="True when this is the principal's default workspace.",
    )
    joined_at: datetime | None = Field(
        default=None,
        description="When the user was added to this workspace, if known.",
    )


class MeContext(BaseSchema):
    """Full bootstrap payload for SPA initialization."""

    user: MeProfile = Field(description="Current principal profile.")
    roles: list[str] = Field(
        default_factory=list,
        description="Global role slugs assigned to the principal.",
    )
    permissions: list[str] = Field(
        default_factory=list,
        description="Global permission keys granted to the principal.",
    )
    workspaces: list[MeWorkspaceSummary] = Field(
        default_factory=list,
        description="Workspaces visible to the principal.",
    )


class EffectivePermissions(BaseSchema):
    """Effective permission sets for the current principal."""

    global_: list[str] = Field(
        default_factory=list,
        alias="global",
        description="Global permission keys granted to the principal.",
    )
    workspaces: dict[UUIDStr, list[str]] = Field(
        default_factory=dict,
        description="Workspace-scoped permissions keyed by workspace id.",
    )


class PermissionCheckRequest(BaseSchema):
    """Payload for checking specific permission keys."""

    permissions: list[str] = Field(
        min_length=1,
        description="Permission keys to evaluate.",
    )
    workspace_id: UUIDStr | None = Field(
        default=None,
        alias="workspace_id",
        description=(
            "Workspace identifier to use when checking workspace-scoped permissions. "
            "Required when any requested permission is workspace-scoped."
        ),
    )


class PermissionCheckResponse(BaseSchema):
    """Result of permission checks for the current principal."""

    results: dict[str, bool] = Field(
        description="Mapping of permission key -> whether it is granted.",
    )


__all__ = [
    "EffectivePermissions",
    "MeContext",
    "MeProfile",
    "MeProfileUpdateRequest",
    "MeWorkspaceSummary",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
]
