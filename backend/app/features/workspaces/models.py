"""Database models for workspace membership."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..users.models import User

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from ..configs.models import Config


class Workspace(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Container grouping documents, configuration, and members."""

    __tablename__ = "workspaces"
    __ulid_field__ = "workspace_id"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    active_config_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("configs.config_id", ondelete="SET NULL"),
        nullable=True,
    )
    active_config: Mapped["Config | None"] = relationship(
        "Config",
        foreign_keys="Workspace.active_config_id",
        lazy="joined",
    )
    configs: Mapped[list["Config"]] = relationship(
        "Config",
        back_populates="workspace",
        cascade="all, delete-orphan",
        foreign_keys="Config.workspace_id",
        primaryjoin="Workspace.id == Config.workspace_id",
    )

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
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="memberships")
    user: Mapped[User] = relationship(User, lazy="joined")
    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id"),
    )


__all__ = ["Workspace", "WorkspaceMembership"]
