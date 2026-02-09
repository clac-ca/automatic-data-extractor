"""ORM models for saved document list views."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_db import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

from .user import User
from .workspace import Workspace


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class DocumentViewVisibility(str, Enum):
    """Visibility scope for saved document views."""

    PRIVATE = "private"
    PUBLIC = "public"


DOCUMENT_VIEW_VISIBILITY_VALUES = tuple(value.value for value in DocumentViewVisibility)


class DocumentView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Saved document list view scoped to a workspace."""

    __tablename__ = "document_views"

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="selectin")

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_key: Mapped[str] = mapped_column(String(120), nullable=False)
    visibility: Mapped[DocumentViewVisibility] = mapped_column(
        SAEnum(
            DocumentViewVisibility,
            name="document_view_visibility",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=True,
    )
    owner_user: Mapped[User | None] = relationship("User", lazy="selectin")

    query_state: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
    )
    table_state: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
    )

    __table_args__ = (
        CheckConstraint(
            "(visibility = 'private' AND owner_user_id IS NOT NULL) OR "
            "(visibility = 'public' AND owner_user_id IS NULL)",
            name="document_views_visibility_owner",
        ),
        Index("ix_document_views_workspace_visibility", "workspace_id", "visibility"),
        Index("ix_document_views_workspace_owner", "workspace_id", "owner_user_id"),
        Index(
            "uq_document_views_workspace_private_owner_name_key",
            "workspace_id",
            "owner_user_id",
            "name_key",
            unique=True,
            postgresql_where=text("visibility = 'private'"),
        ),
        Index(
            "uq_document_views_workspace_public_name_key",
            "workspace_id",
            "name_key",
            unique=True,
            postgresql_where=text("visibility = 'public'"),
        ),
    )


__all__ = [
    "DOCUMENT_VIEW_VISIBILITY_VALUES",
    "DocumentView",
    "DocumentViewVisibility",
]
