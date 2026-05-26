from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_db import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin
from .file import FileComment


class UserNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persistent notification of actions like mentions for users."""

    __tablename__ = "user_notifications"

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    comment_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("file_comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    workspace = relationship("Workspace", lazy="selectin")
    user = relationship("User", lazy="selectin")
    comment: Mapped[FileComment] = relationship("FileComment", lazy="selectin")

    __table_args__ = (
        Index("ix_user_notifications_workspace_user_read", "workspace_id", "user_id", "is_read"),
        Index("ix_user_notifications_workspace_user_created", "workspace_id", "user_id", "created_at"),
        Index("ix_user_notifications_comment_id", "comment_id"),
    )


__all__ = ["UserNotification"]
