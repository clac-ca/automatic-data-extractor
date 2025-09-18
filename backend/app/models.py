"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import ulid
from sqlalchemy import Boolean, Integer, JSON, String, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_ulid() -> str:
    return str(ulid.new())


class ConfigurationRevision(Base):
    """Configuration revision metadata and payloads."""

    __tablename__ = "configuration_revisions"
    __table_args__ = (
        UniqueConstraint(
            "document_type", "revision_number", name="uq_configuration_revision_number"
        ),
    )

    configuration_revision_id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=_generate_ulid
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
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

    def __repr__(self) -> str:
        return (
            "ConfigurationRevision("
            f"configuration_revision_id={self.configuration_revision_id!r}, "
            f"document_type={self.document_type!r}, "
            f"revision_number={self.revision_number!r}"
            ")"
        )


class Job(Base):
    """Processing job metadata and outputs."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    configuration_revision_id: Mapped[str] = mapped_column(String(26), nullable=False)
    configuration_revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(32), default=_timestamp, onupdate=_timestamp, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    outputs: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    logs: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )

    def __repr__(self) -> str:
        return (
            "Job("
            f"job_id={self.job_id!r}, "
            f"document_type={self.document_type!r}, "
            f"configuration_revision_number={self.configuration_revision_number!r}"
            ")"
        )


class Document(Base):
    """Uploaded document metadata with deterministic storage paths."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("sha256", name="uq_document_sha256"),
        UniqueConstraint("stored_uri", name="uq_document_stored_uri"),
    )

    document_id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=_generate_ulid
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(71), nullable=False)
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

    def __repr__(self) -> str:
        return (
            "Document("
            f"document_id={self.document_id!r}, "
            f"original_filename={self.original_filename!r}"
            ")"
        )


__all__ = ["ConfigurationRevision", "Job", "Document"]
