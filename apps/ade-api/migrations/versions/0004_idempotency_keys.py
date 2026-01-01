"""Add idempotency key replay table.

Revision ID: 0004_idempotency_keys
Revises: 0003_search_trgm_indexes
Create Date: 2025-02-14 00:00:02.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from ade_api.db import UUIDType

# revision identifiers, used by Alembic.
revision = "0004_idempotency_keys"
down_revision = "0003_search_trgm_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", UUIDType(), primary_key=True, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_headers", sa.JSON(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("idempotency_key", "scope_key", name="uq_idempotency_scope"),
    )
    op.create_index(
        "ix_idempotency_expires_at",
        "idempotency_keys",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_expires_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
