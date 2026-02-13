"""Access-management models for principal, group, and invitation workflows."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin

from .workspace import Workspace


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class PrincipalType(str, Enum):
    """Principal kind for access assignment targets."""

    USER = "user"
    GROUP = "group"


class AssignmentScopeType(str, Enum):
    """Scope dimension for role assignments."""

    ORGANIZATION = "organization"
    WORKSPACE = "workspace"


class GroupMembershipMode(str, Enum):
    """Group membership control mode."""

    ASSIGNED = "assigned"
    DYNAMIC = "dynamic"


class GroupSource(str, Enum):
    """Source of truth for group lifecycle."""

    INTERNAL = "internal"
    IDP = "idp"


class InvitationStatus(str, Enum):
    """Lifecycle states for invitation records."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"


principal_type_enum = SAEnum(
    PrincipalType,
    name="principal_type",
    native_enum=False,
    length=20,
    values_callable=_enum_values,
)

assignment_scope_type_enum = SAEnum(
    AssignmentScopeType,
    name="assignment_scope_type",
    native_enum=False,
    length=20,
    values_callable=_enum_values,
)

group_membership_mode_enum = SAEnum(
    GroupMembershipMode,
    name="group_membership_mode",
    native_enum=False,
    length=20,
    values_callable=_enum_values,
)

group_source_enum = SAEnum(
    GroupSource,
    name="group_source",
    native_enum=False,
    length=20,
    values_callable=_enum_values,
)

invitation_status_enum = SAEnum(
    InvitationStatus,
    name="invitation_status",
    native_enum=False,
    length=20,
    values_callable=_enum_values,
)


class Group(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Principal container for assigned or provider-managed memberships."""

    __tablename__ = "groups"

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    membership_mode: Mapped[GroupMembershipMode] = mapped_column(
        group_membership_mode_enum,
        nullable=False,
        default=GroupMembershipMode.ASSIGNED,
        server_default=GroupMembershipMode.ASSIGNED.value,
    )
    source: Mapped[GroupSource] = mapped_column(
        group_source_enum,
        nullable=False,
        default=GroupSource.INTERNAL,
        server_default=GroupSource.INTERNAL.value,
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    memberships: Mapped[list[GroupMembership]] = relationship(
        "GroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    owners: Mapped[list[GroupOwner]] = relationship(
        "GroupOwner",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_groups_slug", "slug"),
        Index("ix_groups_source", "source"),
        Index("ix_groups_external_id", "external_id"),
        UniqueConstraint("source", "external_id", name="uq_groups_source_external"),
    )


class GroupMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Explicit relation from user to group."""

    __tablename__ = "group_memberships"

    group_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("groups.id", ondelete="NO ACTION"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    membership_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="internal",
        server_default="internal",
    )

    group: Mapped[Group] = relationship("Group", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_memberships_group_user"),
        Index("ix_group_memberships_group_id", "group_id"),
        Index("ix_group_memberships_user_id", "user_id"),
    )


class GroupOwner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Explicit relation from user to group ownership."""

    __tablename__ = "group_owners"

    group_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("groups.id", ondelete="NO ACTION"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    ownership_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="internal",
        server_default="internal",
    )

    group: Mapped[Group] = relationship("Group", back_populates="owners")

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_owners_group_user"),
        Index("ix_group_owners_group_id", "group_id"),
        Index("ix_group_owners_user_id", "user_id"),
    )


class RoleAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Principal-aware role assignment to organization or workspace scopes."""

    __tablename__ = "role_assignments"

    principal_type: Mapped[PrincipalType] = mapped_column(
        principal_type_enum,
        nullable=False,
    )
    principal_id: Mapped[UUID] = mapped_column(GUID(), nullable=False)
    role_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("roles.id", ondelete="NO ACTION"),
        nullable=False,
    )
    scope_type: Mapped[AssignmentScopeType] = mapped_column(
        assignment_scope_type_enum,
        nullable=False,
    )
    scope_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=True,
    )

    workspace: Mapped[Workspace | None] = relationship("Workspace")

    __table_args__ = (
        UniqueConstraint(
            "principal_type",
            "principal_id",
            "role_id",
            "scope_type",
            "scope_id",
            name="uq_role_assignments_principal_role_scope",
        ),
        Index(
            "uq_role_assignments_org_principal_role",
            "principal_type",
            "principal_id",
            "role_id",
            unique=True,
            postgresql_where=text("scope_type = 'organization' AND scope_id IS NULL"),
        ),
        Index(
            "uq_role_assignments_workspace_principal_role_scope",
            "principal_type",
            "principal_id",
            "role_id",
            "scope_id",
            unique=True,
            postgresql_where=text("scope_type = 'workspace' AND scope_id IS NOT NULL"),
        ),
        Index("ix_role_assignments_principal", "principal_type", "principal_id"),
        Index("ix_role_assignments_scope", "scope_type", "scope_id"),
        Index("ix_role_assignments_role_id", "role_id"),
    )


class Invitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Invitation envelope for workspace-scoped and organization-scoped onboarding."""

    __tablename__ = "invitations"

    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    invited_user_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=True,
    )
    invited_by_user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=True,
    )
    status: Mapped[InvitationStatus] = mapped_column(
        invitation_status_enum,
        nullable=False,
        default=InvitationStatus.PENDING,
        server_default=InvitationStatus.PENDING.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON(),
        nullable=True,
    )
    workspace: Mapped[Workspace | None] = relationship("Workspace")

    __table_args__ = (
        Index("ix_invitations_email_normalized", "email_normalized"),
        Index("ix_invitations_status", "status"),
        Index("ix_invitations_workspace_status_expires", "workspace_id", "status", "expires_at"),
        Index("ix_invitations_workspace_created_id", "workspace_id", "created_at", "id"),
        Index("ix_invitations_invited_user_id", "invited_user_id"),
        Index("ix_invitations_invited_by_user_id", "invited_by_user_id"),
    )


__all__ = [
    "AssignmentScopeType",
    "Group",
    "GroupMembership",
    "GroupOwner",
    "GroupMembershipMode",
    "GroupSource",
    "Invitation",
    "InvitationStatus",
    "PrincipalType",
    "RoleAssignment",
]
