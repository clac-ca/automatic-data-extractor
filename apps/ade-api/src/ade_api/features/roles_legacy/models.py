"""SQLAlchemy models implementing the simplified RBAC schema."""

from __future__ import annotations

from enum import Enum
from uuid import UUID
from typing import cast

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    case,
    false,
    literal,
    true,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from sqlalchemy.ext.hybrid import hybrid_property

from ade_api.shared.db import Base, TimestampMixin, UUIDPrimaryKeyMixin, UUIDType
from ade_api.shared.db.enums import enum_values

from ..users.models import User
from ..workspaces.models import Workspace


class ScopeType(str, Enum):
    """Scope dimensions supported by RBAC."""

    GLOBAL = "global"
    WORKSPACE = "workspace"


class Permission(UUIDPrimaryKeyMixin, Base):
    """Permission definition following the ADE registry."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    resource: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(
            ScopeType,
            name="scope_type",
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


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Role that aggregates permissions for a specific scope."""

    __tablename__ = "roles"

    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(
            ScopeType,
            name="scope_type",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    scope_id: Mapped[UUID | None] = synonym("workspace_id")
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    built_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    editable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_by: Mapped[UUID | None] = mapped_column(UUIDType(), nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(UUIDType(), nullable=True)

    permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["RoleAssignment"]] = relationship(
        "RoleAssignment",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    workspace: Mapped[Workspace | None] = relationship("Workspace")

    __table_args__ = (
        UniqueConstraint("scope_type", "workspace_id", "slug", name="uq_roles_scope_workspace_slug"),
        Index("ix_roles_scope_lookup", "scope_type", "workspace_id"),
    )


class RolePermission(Base):
    """Bridge table linking roles to permissions."""

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    role: Mapped[Role] = relationship("Role", back_populates="permissions")
    permission: Mapped[Permission] = relationship(
        "Permission",
        back_populates="role_permissions",
        lazy="joined",
    )

    __table_args__ = ()


class PrincipalType(str, Enum):
    """Kinds of principals that can hold assignments."""

    USER = "user"


class Principal(Base):
    """Shim mapping principals directly to users."""

    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True)
    user_id: Mapped[UUID] = synonym("id")
    @hybrid_property
    def principal_type(self) -> PrincipalType:
        return PrincipalType.USER

    @principal_type.expression
    def principal_type(cls):
        return literal(PrincipalType.USER.value)

    @property
    def user(self) -> User:
        """Return the underlying user row for compatibility with existing code paths."""
        return cast(User, self)


class RoleAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Assignment of a role to a user at a specific scope."""

    __tablename__ = "user_roles"

    assignment_id: Mapped[UUID] = synonym("id")
    principal_id: Mapped[UUID] = mapped_column(
        "user_id",
        UUIDType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    scope_id: Mapped[UUID | None] = synonym("workspace_id")

    @hybrid_property
    def scope_type(self) -> ScopeType:
        return ScopeType.GLOBAL if self.workspace_id is None else ScopeType.WORKSPACE

    @scope_type.expression
    def scope_type(cls):
        return case(
            (cls.workspace_id.is_(None), ScopeType.GLOBAL.value),
            else_=ScopeType.WORKSPACE.value,
        )

    @scope_type.setter
    def scope_type(self, value: ScopeType) -> None:
        if value == ScopeType.GLOBAL:
            self.workspace_id = None
        elif value == ScopeType.WORKSPACE:
            if self.workspace_id is None:
                self.workspace_id = None
        else:  # pragma: no cover - defensive guard
            msg = f"Unsupported scope_type {value}"
            raise ValueError(msg)

    principal: Mapped[Principal] = relationship(
        Principal,
        primaryjoin="RoleAssignment.principal_id==Principal.id",
        lazy="joined",
    )
    role: Mapped[Role] = relationship("Role", back_populates="assignments")
    user: Mapped[User] = relationship("User", viewonly=True, lazy="joined")
    workspace: Mapped[Workspace | None] = relationship("Workspace")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "workspace_id", name="uq_user_roles_user_role_workspace"),
        Index("ix_user_roles_user_lookup", "user_id", "workspace_id"),
        Index("ix_user_roles_role_lookup", "role_id", "workspace_id"),
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
