"""RBAC models shared across the service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.core.rbac.types import ScopeType
from ade_api.infra.db import Base
from ade_api.infra.db.enums import enum_values
from ade_api.infra.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from ade_api.infra.db.types import UUIDType

from .user import User
from .workspace import Workspace

permission_scope_enum = SAEnum(
    ScopeType,
    name="permission_scope",
    native_enum=False,
    length=20,
    values_callable=enum_values,
)

assignment_scope_enum = SAEnum(
    ScopeType,
    name="rbac_scope",
    native_enum=False,
    length=20,
    values_callable=enum_values,
)


class Permission(UUIDPrimaryKeyMixin, Base):
    """Canonical permission catalog entry."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_type: Mapped[ScopeType] = mapped_column(permission_scope_enum, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Role definition that aggregates permissions."""

    __tablename__ = "roles"

    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_editable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )

    permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[UserRoleAssignment]] = relationship(
        "UserRoleAssignment",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_roles_slug", "slug"),)


class RolePermission(Base):
    """Bridge table linking roles and permissions."""

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("roles.id", ondelete="NO ACTION"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("permissions.id", ondelete="NO ACTION"), primary_key=True
    )

    role: Mapped[Role] = relationship("Role", back_populates="permissions")
    permission: Mapped[Permission] = relationship(
        "Permission",
        back_populates="role_permissions",
        lazy="joined",
    )

    __table_args__ = ()


class UserRoleAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Assignment of a role to a user within a scope."""

    __tablename__ = "user_role_assignments"

    user_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("roles.id", ondelete="NO ACTION"), nullable=False
    )
    scope_type: Mapped[ScopeType] = mapped_column(
        assignment_scope_enum,
        nullable=False,
    )
    scope_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=True
    )

    user: Mapped[User] = relationship("User")
    role: Mapped[Role] = relationship("Role", back_populates="assignments")
    workspace: Mapped[Workspace | None] = relationship("Workspace")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "role_id",
            "scope_type",
            "scope_id",
            name="uq_user_role_scope",
        ),
        CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="chk_user_role_scope",
        ),
        Index("ix_user_scope", "user_id", "scope_type", "scope_id"),
        Index("ix_role_scope", "role_id", "scope_type", "scope_id"),
    )


__all__ = [
    "Permission",
    "Role",
    "RolePermission",
    "ScopeType",
    "UserRoleAssignment",
]
