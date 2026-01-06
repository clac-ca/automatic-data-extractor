"""Document change feed refactor (versioning + upload sessions).

Notes:
- Adds document versioning for optimistic concurrency.
- Extends document_changes with document_version + client_request_id.
- Reserves document_id for upload sessions.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import CHAR, TypeDecorator

# Revision identifiers, used by Alembic.
revision = "0002_document_change_feed_refactor"
down_revision: Optional[str] = "0001_initial_schema"
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


def _dialect_name() -> Optional[str]:
    try:
        bind = op.get_bind()
    except Exception:
        return None
    return bind.dialect.name if bind is not None else None


def _document_status_enum(*values: str) -> sa.Enum:
    return sa.Enum(
        *values,
        name="document_status",
        native_enum=False,
        create_constraint=True,
        length=20,
    )


def _update_document_status_constraint(dialect: str | None) -> None:
    if dialect != "mssql":
        return

    values = ("uploading", "uploaded", "processing", "processed", "failed", "archived")
    op.execute("ALTER TABLE documents DROP CONSTRAINT document_status")
    op.execute(
        "ALTER TABLE documents ADD CONSTRAINT document_status "
        f"CHECK (status IN ({', '.join(repr(value) for value in values)}))"
    )


def upgrade() -> None:
    dialect = _dialect_name()

    if dialect == "sqlite":
        with op.batch_alter_table("documents") as batch_op:
            batch_op.add_column(
                sa.Column("version", sa.Integer(), nullable=False, server_default="1")
            )
            batch_op.alter_column(
                "status",
                existing_type=_document_status_enum(
                    "uploaded", "processing", "processed", "failed", "archived"
                ),
                type_=_document_status_enum(
                    "uploading", "uploaded", "processing", "processed", "failed", "archived"
                ),
                existing_nullable=False,
                existing_server_default="uploaded",
                server_default="uploaded",
            )
    else:
        op.add_column(
            "documents",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        _update_document_status_constraint(dialect)

    op.add_column(
        "document_changes",
        sa.Column("document_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_changes",
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
    )

    op.add_column(
        "document_upload_sessions",
        sa.Column("document_id", GUID(), nullable=True),
    )
    op.create_index(
        "ix_document_upload_sessions_document",
        "document_upload_sessions",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")

