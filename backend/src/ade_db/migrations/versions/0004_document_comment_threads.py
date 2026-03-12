"""Add document activity threads and range-based comment mentions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0004_document_comment_threads"
down_revision = "0003_invitation_lifecycle_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    anchor_type = sa.Enum(
        "note",
        "document",
        "run",
        name="document_activity_thread_anchor_type",
        native_enum=False,
        length=20,
    )
    anchor_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "document_activity_threads",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("anchor_type", anchor_type, nullable=False),
        sa.Column("anchor_id", sa.UUID(), nullable=True),
        sa.Column("activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("uuidv7()")),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_activity_threads")),
    )
    op.create_index(
        "ix_document_activity_threads_file_activity",
        "document_activity_threads",
        ["file_id", "activity_at"],
        unique=False,
    )
    op.create_index(
        "ix_document_activity_threads_workspace_activity",
        "document_activity_threads",
        ["workspace_id", "activity_at"],
        unique=False,
    )
    op.create_index(
        "uq_document_activity_threads_anchor",
        "document_activity_threads",
        ["file_id", "anchor_type", "anchor_id"],
        unique=True,
        postgresql_where=sa.text("anchor_id IS NOT NULL"),
    )

    op.add_column(
        "file_comments",
        sa.Column("thread_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_file_comments_thread_created",
        "file_comments",
        ["thread_id", "created_at"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_file_comments_thread_id_document_activity_threads"),
        "file_comments",
        "document_activity_threads",
        ["thread_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column(
        "file_comment_mentions",
        sa.Column("start_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "file_comment_mentions",
        sa.Column("end_index", sa.Integer(), nullable=False, server_default="1"),
    )

    op.execute(
        """
        CREATE TEMP TABLE _document_comment_thread_map AS
        SELECT id AS comment_id, uuidv7() AS thread_id
        FROM file_comments;
        """
    )
    op.execute(
        """
        INSERT INTO document_activity_threads (
            id,
            workspace_id,
            file_id,
            anchor_type,
            anchor_id,
            activity_at,
            created_at,
            updated_at
        )
        SELECT
            map.thread_id,
            comment.workspace_id,
            comment.file_id,
            'note',
            NULL,
            comment.created_at,
            comment.created_at,
            comment.updated_at
        FROM file_comments AS comment
        JOIN _document_comment_thread_map AS map
          ON map.comment_id = comment.id;
        """
    )
    op.execute(
        """
        UPDATE file_comments AS comment
        SET thread_id = map.thread_id
        FROM _document_comment_thread_map AS map
        WHERE map.comment_id = comment.id;
        """
    )
    op.execute("DROP TABLE _document_comment_thread_map;")

    # Existing mention rows do not store ranges, so they cannot be migrated reliably.
    op.execute("DELETE FROM file_comment_mentions;")

    op.alter_column("file_comments", "thread_id", nullable=False)
    op.alter_column("file_comment_mentions", "start_index", server_default=None)
    op.alter_column("file_comment_mentions", "end_index", server_default=None)

    op.drop_constraint(
        "file_comment_mentions_comment_user_key",
        "file_comment_mentions",
        type_="unique",
    )
    op.create_unique_constraint(
        "file_comment_mentions_comment_user_key",
        "file_comment_mentions",
        ["comment_id", "mentioned_user_id", "start_index", "end_index"],
    )
    op.create_index(
        "ix_file_comment_mentions_comment_start",
        "file_comment_mentions",
        ["comment_id", "start_index"],
        unique=False,
    )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
