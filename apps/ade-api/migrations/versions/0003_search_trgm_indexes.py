"""Add trigram indexes for q search.

Revision ID: 0003_search_trgm_indexes
Revises: 0002_run_queue_refactor
Create Date: 2025-02-14 00:00:01.000000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_search_trgm_indexes"
down_revision = "0002_run_queue_refactor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_index(
        "ix_documents_name_trgm",
        "documents",
        ["original_filename"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"original_filename": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_users_email_trgm",
        "users",
        ["email"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"email": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_users_display_name_trgm",
        "users",
        ["display_name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"display_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_configurations_display_name_trgm",
        "configurations",
        ["display_name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"display_name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("ix_configurations_display_name_trgm", table_name="configurations")
    op.drop_index("ix_users_display_name_trgm", table_name="users")
    op.drop_index("ix_users_email_trgm", table_name="users")
    op.drop_index("ix_documents_name_trgm", table_name="documents")
