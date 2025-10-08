"""SQLAlchemy models for RBAC tables."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from .registry import PermissionScope


class Permission(Base):
    """Database record for a permission registry entry."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    scope: Mapped[PermissionScope] = mapped_column(
        Enum("global", "workspace", name="permissionscope", native_enum=False, length=20),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class Role(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-wide or workspace-scoped role."""

    __tablename__ = "roles"
    __ulid_field__ = "role_id"

    scope: Mapped[PermissionScope] = mapped_column(
        Enum("global", "workspace", name="rolescope", native_enum=False, length=20),
        nullable=False,
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(26), nullable=True)

    permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    user_assignments: Mapped[list["UserGlobalRole"]] = relationship(
        "UserGlobalRole",
        back_populates="role",
        cascade="all, delete-orphan",
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
    permission: Mapped[Permission] = relationship("Permission", back_populates="role_permissions")


class UserGlobalRole(Base):
    """Assignment of a global role to a user."""

    __tablename__ = "user_global_roles"

    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True
    )

    role: Mapped[Role] = relationship("Role", back_populates="user_assignments")


__all__ = ["Permission", "Role", "RolePermission", "UserGlobalRole"]
