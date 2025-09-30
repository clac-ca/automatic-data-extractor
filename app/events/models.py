from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.mixins import ULIDPrimaryKeyMixin


class Event(ULIDPrimaryKeyMixin, Base):
    """Domain event persisted for audit trails and timelines."""

    __tablename__ = "events"
    __ulid_field__ = "event_id"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


__all__ = ["Event"]
