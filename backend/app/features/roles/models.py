"""SQLAlchemy models implementing the unified RBAC schema."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..users.models import User

ScopeTypeEnum = Enum(
    "global",
    "workspace",
    name="scopetype",
    native_enum=False,
    length=20,
)

PrincipalTypeEnum = Enum(
    "user",
    name="principaltype",
    native_enum=False,
    length=20,
)


class Principal(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Subject that can receive role assignments."""

    __tablename__ = "principals"
    __ulid_field__ = "principal_id"

    principal_type: Mapped[str] = mapped_column(
        PrincipalTypeEnum, nullable=False, default="user"
    )
    user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True
    )

    user: Mapped[User | None] = relationship(
        User, back_populates="principal", lazy="joined"
    )
    assignments: Mapped[list["RoleAssignment"]] = relationship(
        "RoleAssignment",
        back_populates="principal",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "(principal_type = 'user' AND user_id IS NOT NULL)",
            name="principals_user_fk_required",
        ),
    )


class Permission(Base):
    """Permission definition following the ADE registry."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    resource: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_type: Mapped[str] = mapped_column(ScopeTypeEnum, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class Role(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Role that aggregates permissions for a specific scope."""

    __tablename__ = "roles"
    __ulid_field__ = "role_id"

    scope_type: Mapped[str] = mapped_column(ScopeTypeEnum, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    built_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(26), nullable=True)

    permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["RoleAssignment"]] = relationship(
        "RoleAssignment",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "slug"),
    )


class RolePermission(Base):
    """Bridge table linking roles to permissions."""

    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True
    )
    permission_key: Mapped[str] = mapped_column(
        String(120), ForeignKey("permissions.key", ondelete="CASCADE"), primary_key=True
    )

    role: Mapped[Role] = relationship("Role", back_populates="permissions")
    permission: Mapped[Permission] = relationship(
        "Permission", back_populates="role_permissions"
    )


class RoleAssignment(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Assignment of a role to a principal at a specific scope."""

    __tablename__ = "role_assignments"
    __ulid_field__ = "assignment_id"

    principal_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("principals.principal_id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(ScopeTypeEnum, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=True
    )

    principal: Mapped[Principal] = relationship(
        "Principal", back_populates="assignments"
    )
    role: Mapped[Role] = relationship("Role", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("principal_id", "role_id", "scope_type", "scope_id"),
        CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR"
            " (scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="role_assignments_scope_consistency",
        ),
    )


__all__ = [
    "Permission",
    "Principal",
    "Role",
    "RoleAssignment",
    "RolePermission",
]

