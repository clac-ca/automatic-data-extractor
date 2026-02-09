"""Workspace and membership models shared across features."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.db import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

from .user import User


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Container grouping documents and workspace members."""

    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
    )
    memberships: Mapped[list[WorkspaceMembership]] = relationship(
        "WorkspaceMembership",
        back_populates="workspace",
    )


class WorkspaceMembership(TimestampMixin, Base):
    """Assignment of a user to a workspace with role/permission metadata."""

    __tablename__ = "workspace_memberships"
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True
    )
    workspace_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="NO ACTION"), primary_key=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="memberships")
    user: Mapped[User] = relationship(User, lazy="joined")
    __table_args__ = ()


__all__ = ["Workspace", "WorkspaceMembership"]
