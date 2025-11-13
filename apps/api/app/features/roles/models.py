"""SQLAlchemy models implementing the unified RBAC schema."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin
from apps.api.app.shared.db.enums import enum_values

from ..users.models import User


class ScopeType(str, Enum):
    """Scope dimensions supported by RBAC."""

    GLOBAL = "global"
    WORKSPACE = "workspace"


class PrincipalType(str, Enum):
    """Kinds of principals that can hold assignments."""

    USER = "user"


class Principal(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Subject that can receive role assignments."""

    __tablename__ = "principals"
    principal_type: Mapped[PrincipalType] = mapped_column(
        SAEnum(
            PrincipalType,
            name="principal_type",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=PrincipalType.USER,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    user: Mapped[User | None] = relationship(
        User, back_populates="principal", lazy="joined"
    )
    assignments: Mapped[list[RoleAssignment]] = relationship(
        "RoleAssignment",
        back_populates="principal",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            f"(principal_type = '{PrincipalType.USER.value}' AND user_id IS NOT NULL)",
            name="principals_user_fk_required",
        ),
    )


class Permission(ULIDPrimaryKeyMixin, Base):
    """Permission definition following the ADE registry."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    resource: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(
            ScopeType,
            name="permission_scope_type",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class Role(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Role that aggregates permissions for a specific scope."""

    __tablename__ = "roles"
    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(
            ScopeType,
            name="role_scope_type",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    scope_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    built_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(26), nullable=True)

    permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[RoleAssignment]] = relationship(
        "RoleAssignment",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "slug"),
    )


class RolePermission(ULIDPrimaryKeyMixin, Base):
    """Bridge table linking roles to permissions."""

    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[Role] = relationship("Role", back_populates="permissions")
    permission: Mapped[Permission] = relationship(
        "Permission",
        back_populates="role_permissions",
        lazy="joined",
    )

    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)


class RoleAssignment(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Assignment of a role to a principal at a specific scope."""

    __tablename__ = "role_assignments"
    principal_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("principals.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(
            ScopeType,
            name="assignment_scope_type",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    scope_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )

    principal: Mapped[Principal] = relationship(
        "Principal", back_populates="assignments"
    )
    role: Mapped[Role] = relationship("Role", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("principal_id", "role_id", "scope_type", "scope_id"),
        CheckConstraint(
            f"(scope_type = '{ScopeType.GLOBAL.value}' AND scope_id IS NULL) OR"
            f" (scope_type = '{ScopeType.WORKSPACE.value}' AND scope_id IS NOT NULL)",
            name="role_assignments_scope_consistency",
        ),
    )


__all__ = [
    "Permission",
    "Principal",
    "PrincipalType",
    "Role",
    "RoleAssignment",
    "RolePermission",
    "ScopeType",
]
