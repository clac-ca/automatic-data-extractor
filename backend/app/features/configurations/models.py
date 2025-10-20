"""SQLAlchemy models for configuration metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..workspaces.models import Workspace
from ..users.models import User


class Configuration(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned configuration payloads for document processing."""

    __tablename__ = "configurations"
    __ulid_field__ = "configuration_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="joined")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "version"),
        Index(
            "configurations_workspace_active_idx",
            "workspace_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    script_versions: Mapped[list["ConfigurationScriptVersion"]] = relationship(
        "ConfigurationScriptVersion",
        back_populates="configuration",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    columns: Mapped[list["ConfigurationColumn"]] = relationship(
        "ConfigurationColumn",
        back_populates="configuration",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ConfigurationScriptVersion(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable script versions scoped to a configuration and canonical key."""

    __tablename__ = "configuration_script_versions"
    __ulid_field__ = "script_version_id"

    configuration_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("configurations.configuration_id", ondelete="CASCADE"),
        nullable=False,
    )
    configuration: Mapped[Configuration] = relationship(
        "Configuration",
        back_populates="script_versions",
    )

    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="python")
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_name: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_declared_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    validation_errors: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[User | None] = relationship("User")

    columns: Mapped[list["ConfigurationColumn"]] = relationship(
        "ConfigurationColumn",
        back_populates="script_version",
    )

    __table_args__ = (
        UniqueConstraint("configuration_id", "canonical_key", "version"),
        Index(
            "configuration_script_versions_config_canonical_idx",
            "configuration_id",
            "canonical_key",
        ),
    )


class ConfigurationColumn(TimestampMixin, Base):
    """Column metadata and optional binding to a configuration script version."""

    __tablename__ = "configuration_columns"

    configuration_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("configurations.configuration_id", ondelete="CASCADE"),
        primary_key=True,
    )
    canonical_key: Mapped[str] = mapped_column(String(255), primary_key=True)

    configuration: Mapped[Configuration] = relationship(
        "Configuration",
        back_populates="columns",
    )

    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    display_label: Mapped[str] = mapped_column(String(255), nullable=False)
    header_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    script_version_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey(
            "configuration_script_versions.script_version_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    script_version: Mapped[ConfigurationScriptVersion | None] = relationship(
        "ConfigurationScriptVersion",
        back_populates="columns",
    )
    params: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        default=dict,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("configuration_id", "ordinal"),
        Index(
            "configuration_columns_config_ordinal_idx",
            "configuration_id",
            "ordinal",
        ),
    )


__all__ = [
    "Configuration",
    "ConfigurationColumn",
    "ConfigurationScriptVersion",
]
