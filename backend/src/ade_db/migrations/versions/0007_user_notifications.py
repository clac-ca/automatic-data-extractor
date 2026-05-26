"""Add user_notifications table for persistent in-app notifications.

Revision ID: 0007_user_notifications
Revises: 0006_run_field_valid_cells
Create Date: 2026-05-26 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0007_user_notifications"
down_revision = "0006_run_field_valid_cells"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_notifications",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("comment_id", sa.UUID(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("uuidv7()")),
        sa.ForeignKeyConstraint(["comment_id"], ["file_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_notifications")),
    )
    op.create_index(
        "ix_user_notifications_workspace_user_read",
        "user_notifications",
        ["workspace_id", "user_id", "is_read"],
        unique=False,
    )
    op.create_index(
        "ix_user_notifications_workspace_user_created",
        "user_notifications",
        ["workspace_id", "user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_notifications_comment_id",
        "user_notifications",
        ["comment_id"],
        unique=False,
    )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
