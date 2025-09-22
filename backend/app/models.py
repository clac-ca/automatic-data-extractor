"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from ulid import ULID
from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_ulid() -> str:
    return str(ULID())


class UserRole(StrEnum):
    """Role assigned to ADE users."""

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class Configuration(Base):
    """Configuration metadata and versioned payloads."""

    __tablename__ = "configurations"

    configuration_id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=_generate_ulid
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activated_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Persist arbitrary structured data. Callers should reassign ``payload``
    # instead of mutating nested keys so change tracking stays predictable.
    payload: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(32), default=_timestamp, onupdate=_timestamp, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("document_type", "version"),
        Index(
            "uq_configuration_active_per_document_type",
            "document_type",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    def __repr__(self) -> str:
        return (
            "Configuration("
            f"configuration_id={self.configuration_id!r}, "
            f"document_type={self.document_type!r}, "
            f"version={self.version!r}"
            ")"
        )


class Job(Base):
    """Processing job metadata and configuration details."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    configuration_id: Mapped[str] = mapped_column(String(26), nullable=False)
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(32), default=_timestamp, onupdate=_timestamp, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    input_document_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("documents.document_id"), nullable=False
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    logs: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )

    __table_args__ = (Index("ix_jobs_input_document_id", "input_document_id"),)

    def __repr__(self) -> str:
        return (
            "Job("
            f"job_id={self.job_id!r}, "
            f"document_type={self.document_type!r}, "
            f"configuration_version={self.configuration_version!r}"
            ")"
        )


class Document(Base):
    """Uploaded document metadata with deterministic storage paths."""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=_generate_ulid
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSON),
        default=dict,
        nullable=False,
    )
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(32), default=_timestamp, onupdate=_timestamp, nullable=False
    )
    deleted_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    produced_by_job_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("jobs.job_id"), nullable=True
    )

    __table_args__ = (
        Index("ix_documents_produced_by_job_id", "produced_by_job_id"),
    )

    def __repr__(self) -> str:
        return (
            "Document("
            f"document_id={self.document_id!r}, "
            f"original_filename={self.original_filename!r}"
            ")"
        )


class Event(Base):
    """Immutable record of actions performed against ADE entities."""

    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=_generate_ulid
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )

    __table_args__ = (
        Index("ix_events_entity", "entity_type", "entity_id"),
        Index("ix_events_event_type", "event_type"),
    )

    def __repr__(self) -> str:
        return (
            "Event("
            f"event_id={self.event_id!r}, "
            f"event_type={self.event_type!r}, "
            f"entity_type={self.entity_type!r}, "
            f"entity_id={self.entity_id!r}"
            ")"
        )


class MaintenanceStatus(Base):
    """Keyed storage for maintenance metadata payloads."""

    __tablename__ = "maintenance_status"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(32), default=_timestamp, onupdate=_timestamp, nullable=False
    )

    def __repr__(self) -> str:
        return f"MaintenanceStatus(key={self.key!r})"


class User(Base):
    """Registered ADE operator."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=_generate_ulid
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20),
        default=UserRole.VIEWER,
        nullable=False,
    )
    sso_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sso_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(32), default=_timestamp, onupdate=_timestamp, nullable=False
    )
    last_login_at: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (UniqueConstraint("sso_provider", "sso_subject"),)

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id!r}, email={self.email!r})"


__all__ = [
    "Configuration",
    "Job",
    "Document",
    "Event",
    "MaintenanceStatus",
    "User",
    "UserRole",
]
