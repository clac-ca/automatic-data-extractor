"""Database models for workspace membership."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...db import Base
from ...db.mixins import TimestampMixin, ULIDPrimaryKeyMixin
from ..users.models import User


class WorkspaceRole(StrEnum):
    """Roles that govern workspace-level permissions."""

    MEMBER = "member"
    OWNER = "owner"


class Workspace(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Container grouping documents, configuration, and members."""

    __tablename__ = "workspaces"
    __ulid_field__ = "workspace_id"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    memberships: Mapped[list[WorkspaceMembership]] = relationship(
        "WorkspaceMembership",
        back_populates="workspace",
    )


class WorkspaceMembership(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Assignment of a user to a workspace with role/permission metadata."""

    __tablename__ = "workspace_memberships"
    __ulid_field__ = "workspace_membership_id"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole, name="workspacerole", native_enum=False, length=20),
        nullable=False,
        default=WorkspaceRole.MEMBER,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="memberships")
    user: Mapped[User] = relationship(User, lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id"),
    )


__all__ = ["Workspace", "WorkspaceMembership", "WorkspaceRole"]
