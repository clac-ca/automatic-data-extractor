"""Add versioned build metadata for venv refactor."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0002_ade_venv_refactor"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _add_build_columns()
    _add_configuration_columns()


def downgrade() -> None:  # pragma: no cover
    """Downgrade is intentionally unsupported."""
    raise NotImplementedError("Downgrade is not supported for this revision.")


def _add_build_columns() -> None:
    op.add_column(
        "builds",
        sa.Column("fingerprint", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "builds",
        sa.Column("engine_spec", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "builds",
        sa.Column("engine_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "builds",
        sa.Column("python_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "builds",
        sa.Column("python_interpreter", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "builds",
        sa.Column("config_digest", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_builds_fingerprint", "builds", ["fingerprint"], unique=False)


def _add_configuration_columns() -> None:
    build_status = sa.Enum(
        "queued",
        "building",
        "active",
        "failed",
        "canceled",
        name="configuration_active_build_status",
        native_enum=False,
        length=20,
        create_constraint=True,
    )
    bind = op.get_bind()
    build_status.create(bind, checkfirst=True)

    op.add_column(
        "configurations",
        sa.Column("active_build_id", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "configurations",
        sa.Column("active_build_fingerprint", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "configurations",
        sa.Column("active_build_status", build_status, nullable=True),
    )
    op.add_column(
        "configurations",
        sa.Column("active_build_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "configurations",
        sa.Column("active_build_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "configurations",
        sa.Column("active_build_error", sa.Text(), nullable=True),
    )
