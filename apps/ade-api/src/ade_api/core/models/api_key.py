"""API key model aligned with the current schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.core.rbac.types import ScopeType
from ade_api.infra.db import Base, TimestampMixin, UUIDPrimaryKeyMixin
from ade_api.infra.db.enums import enum_values
from ade_api.infra.db.types import UUIDType

from .user import User
from .workspace import Workspace


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored representation of an issued API key."""

    __tablename__ = "api_keys"

    owner_user_id: Mapped[UUID] = mapped_column(
        "owner_user_id",
        UUIDType(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        "created_by_user_id",
        UUIDType(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=True,
    )
    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(
            ScopeType,
            name="rbac_scope",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ScopeType.GLOBAL,
    )
    scope_id: Mapped[UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=True,
    )
    token_prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_used_user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    owner: Mapped[User | None] = relationship(
        User,
        foreign_keys=[owner_user_id],
        lazy="joined",
    )
    created_by: Mapped[User | None] = relationship(
        User,
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )
    workspace: Mapped[Workspace | None] = relationship(Workspace)

    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type = 'workspace' AND scope_id IS NOT NULL)",
            name="chk_api_key_scope",
        ),
        Index(
            "ix_api_keys_owner_scope",
            "owner_user_id",
            "scope_type",
            "scope_id",
        ),
    )


__all__ = ["ApiKey"]
