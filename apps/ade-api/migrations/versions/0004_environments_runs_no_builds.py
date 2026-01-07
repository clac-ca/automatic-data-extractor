"""Runs + environments schema (remove builds)."""

from __future__ import annotations

import uuid
from typing import Any, Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import CHAR, TypeDecorator

# Revision identifiers, used by Alembic.
revision = "0004_environments_runs_no_builds"
down_revision: Optional[str] = "0003_document_events"
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


ENVIRONMENT_STATUS = sa.Enum(
    "queued",
    "building",
    "ready",
    "failed",
    name="environment_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind is not None else "unknown"

    # Add environments table.
    op.create_table(
        "environments",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("configuration_id", GUID(), sa.ForeignKey("configurations.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("engine_spec", sa.String(length=255), nullable=False),
        sa.Column("deps_digest", sa.String(length=128), nullable=False),
        sa.Column("status", ENVIRONMENT_STATUS, nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("claimed_by", sa.String(length=255), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("python_version", sa.String(length=50), nullable=True),
        sa.Column("python_interpreter", sa.String(length=512), nullable=True),
        sa.Column("engine_version", sa.String(length=50), nullable=True),
        sa.UniqueConstraint(
            "workspace_id",
            "configuration_id",
            "engine_spec",
            "deps_digest",
            name="ux_environments_key",
        ),
    )
    op.create_index("ix_environments_workspace", "environments", ["workspace_id"], unique=False)
    op.create_index("ix_environments_configuration", "environments", ["configuration_id"], unique=False)
    op.create_index("ix_environments_claim", "environments", ["status", "created_at"], unique=False)
    op.create_index("ix_environments_claim_expires", "environments", ["status", "claim_expires_at"], unique=False)
    op.create_index("ix_environments_status_last_used", "environments", ["status", "last_used_at"], unique=False)
    op.create_index("ix_environments_status_updated", "environments", ["status", "updated_at"], unique=False)

    # Update configurations: drop build pointers.
    if dialect_name == "sqlite":
        with op.batch_alter_table("configurations", recreate="always") as batch:
            batch.drop_index("ix_configurations_active_build_id")
            batch.drop_column("active_build_id")
            batch.drop_column("active_build_fingerprint")
    else:
        op.drop_index("ix_configurations_active_build_id", table_name="configurations")
        op.drop_column("configurations", "active_build_id")
        op.drop_column("configurations", "active_build_fingerprint")

    # Update runs: drop build_id + cancelled_at, add env selectors.
    if dialect_name == "sqlite":
        with op.batch_alter_table("runs", recreate="always") as batch:
            batch.drop_index("ix_runs_build")
            batch.drop_column("build_id")
            batch.drop_column("cancelled_at")
            batch.add_column(
                sa.Column(
                    "engine_spec",
                    sa.String(length=255),
                    nullable=False,
                    server_default=sa.text("'apps/ade-engine'"),
                ),
            )
            batch.add_column(
                sa.Column(
                    "deps_digest",
                    sa.String(length=128),
                    nullable=False,
                    server_default=sa.text(
                        "'sha256:2e1cfa82b035c26cbbbdae632cea070514eb8b773f616aaeaf668e2f0be8f10d'"
                    ),
                ),
            )
            batch.create_index("ix_runs_claim_expires", ["status", "claim_expires_at"], unique=False)
            batch.create_index("ix_runs_status_completed", ["status", "completed_at"], unique=False)
    else:
        op.drop_index("ix_runs_build", table_name="runs")
        op.drop_column("runs", "build_id")
        op.drop_column("runs", "cancelled_at")
        op.add_column(
            "runs",
            sa.Column(
                "engine_spec",
                sa.String(length=255),
                nullable=False,
                server_default=sa.text("'apps/ade-engine'"),
            ),
        )
        op.add_column(
            "runs",
            sa.Column(
                "deps_digest",
                sa.String(length=128),
                nullable=False,
                server_default=sa.text(
                    "'sha256:2e1cfa82b035c26cbbbdae632cea070514eb8b773f616aaeaf668e2f0be8f10d'"
                ),
            ),
        )
        op.create_index("ix_runs_claim_expires", "runs", ["status", "claim_expires_at"], unique=False)
        op.create_index("ix_runs_status_completed", "runs", ["status", "completed_at"], unique=False)

    # Remove builds table.
    op.drop_table("builds")


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
