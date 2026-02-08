"""Add configuration provenance and notes fields.

Revision ID: 0005_config_provenance_notes
Revises: 0004_auth_session_auth_method
Create Date: 2026-02-08
"""

from __future__ import annotations

from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005_config_provenance_notes"
down_revision = "0004_auth_session_auth_method"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    source_kind_enum = sa.Enum(
        "template",
        "import",
        "clone",
        "restore",
        name="configuration_source_kind",
        native_enum=False,
        length=20,
    )

    op.add_column(
        "configurations",
        sa.Column(
            "source_configuration_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "configurations",
        sa.Column(
            "source_kind",
            source_kind_enum,
            nullable=True,
            server_default="template",
        ),
    )
    op.add_column(
        "configurations",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_configurations_source_configuration_id_configurations",
        "configurations",
        "configurations",
        ["source_configuration_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_configurations_workspace_source",
        "configurations",
        ["workspace_id", "source_configuration_id"],
    )

    op.execute(
        "UPDATE configurations SET source_kind = 'template' WHERE source_kind IS NULL"
    )
    op.alter_column("configurations", "source_kind", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_configurations_workspace_source", table_name="configurations")
    op.drop_constraint(
        "fk_configurations_source_configuration_id_configurations",
        "configurations",
        type_="foreignkey",
    )
    op.drop_column("configurations", "notes")
    op.drop_column("configurations", "source_kind")
    op.drop_column("configurations", "source_configuration_id")
