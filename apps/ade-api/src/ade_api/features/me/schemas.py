"""Schemas for the `/me` feature."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class MeProfile(BaseModel):
    """Minimal profile for the currently authenticated principal."""

    id: UUID = Field(..., description="Unique user identifier.")
    email: EmailStr = Field(..., description="Primary email address.")
    display_name: str | None = Field(
        default=None, description="Human-friendly name for display."
    )
    is_service_account: bool = Field(
        ..., description="True when this principal is a service account."
    )
    created_at: datetime = Field(..., description="User creation timestamp.")
    updated_at: datetime | None = Field(
        default=None, description="Timestamp of last profile update, if any."
    )


class MeWorkspaceSummary(BaseModel):
    """Lightweight view of a workspace visible to the current principal."""

    id: UUID = Field(..., description="Workspace identifier.")
    name: str = Field(..., description="Workspace display name.")
    slug: str | None = Field(
        default=None, description="Optional URL-friendly slug for the workspace."
    )
    is_default: bool = Field(
        ..., description="True when this is the principal's default workspace."
    )
    joined_at: datetime | None = Field(
        default=None, description="When the user was added to this workspace, if known."
    )


class MeWorkspacePage(BaseModel):
    """Paged collection of workspaces for the current principal."""

    items: list[MeWorkspaceSummary] = Field(..., description="Workspace entries.")
    page: int = Field(..., ge=1, description="Current page (1-based).")
    page_size: int = Field(..., ge=1, description="Page size used for the query.")
    total: int | None = Field(
        default=None,
        ge=0,
        description="Total number of workspaces, when requested.",
    )
    has_next: bool = Field(..., description="True when a subsequent page exists.")
    has_previous: bool = Field(
        ..., description="True when a previous page exists."
    )


class MeContext(BaseModel):
    """Full bootstrap payload for SPA initialization."""

    user: MeProfile = Field(..., description="Current principal profile.")
    global_roles: list[str] = Field(
        default_factory=list,
        description="Slugs of global roles assigned to the principal.",
    )
    global_permissions: list[str] = Field(
        default_factory=list,
        description="Global permission keys granted to the principal.",
    )
    workspaces: MeWorkspacePage = Field(
        ..., description="Workspaces visible to the principal."
    )


class EffectivePermissions(BaseModel):
    """Effective permission sets for the current principal."""

    global_permissions: list[str] = Field(
        ..., description="Global permission keys granted to the principal."
    )
    workspace_id: UUID | None = Field(
        default=None,
        description="Workspace for which workspace_permissions were evaluated.",
    )
    workspace_permissions: list[str] = Field(
        default_factory=list,
        description=(
            "Workspace-scoped permission keys granted to the principal "
            "for the specified workspace."
        ),
    )


class PermissionCheckRequest(BaseModel):
    """Payload for checking specific permission keys."""

    permissions: list[str] = Field(
        ..., min_length=1, description="Permission keys to evaluate."
    )
    workspace_id: UUID | None = Field(
        default=None,
        description=(
            "Workspace identifier to use when checking workspace-scoped permissions. "
            "Required when any requested permission is workspace-scoped."
        ),
    )


class PermissionCheckResponse(BaseModel):
    """Result of permission checks for the current principal."""

    results: dict[str, bool] = Field(
        ..., description="Mapping of permission key -> whether it is granted."
    )


__all__ = [
    "EffectivePermissions",
    "MeContext",
    "MeProfile",
    "MeWorkspacePage",
    "MeWorkspaceSummary",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
]
