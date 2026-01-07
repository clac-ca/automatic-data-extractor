"""Simplified document change feed (document_events).

Notes:
- Drops legacy document_changes table.
- Creates document_events with minimal event payloads.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import CHAR, TypeDecorator

# Revision identifiers, used by Alembic.
revision = "0003_document_events"
down_revision: Optional[str] = "0002_document_change_feed_refactor"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


class GUID(TypeDecorator):
    """SQLite + SQL Server GUID storage."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any):
        if dialect.name == "mssql":
            from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect: Any):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    @property
    def python_type(self) -> type[uuid.UUID]:
        return uuid.UUID


DOCUMENT_EVENT_TYPE = sa.Enum(
    "document.changed",
    "document.deleted",
    name="document_event_type",
    native_enum=False,
    create_constraint=True,
    length=40,
)


def upgrade() -> None:
    op.drop_table("document_changes")

    op.create_table(
        "document_events",
        sa.Column(
            "cursor",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("event_type", DOCUMENT_EVENT_TYPE, nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_events_workspace_cursor", "document_events", ["workspace_id", "cursor"], unique=False)
    op.create_index("ix_document_events_workspace_document", "document_events", ["workspace_id", "document_id"], unique=False)
    op.create_index("ix_document_events_workspace_occurred", "document_events", ["workspace_id", "occurred_at"], unique=False)


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")

