"""Initial ADE schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configurations",
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activated_at", sa.String(length=32), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("configuration_id"),
        sa.UniqueConstraint("document_type", "version"),
    )
    op.create_index(
        "configurations_document_type_active_idx",
        "configurations",
        ["document_type"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
    )

    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(length=26), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_uri", sa.String(length=512), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("deleted_at", sa.String(length=32), nullable=True),
        sa.Column("deleted_by", sa.String(length=100), nullable=True),
        sa.Column("delete_reason", sa.String(length=1024), nullable=True),
        sa.Column("produced_by_job_id", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "documents_produced_by_job_id_idx",
        "documents",
        ["produced_by_job_id"],
        unique=False,
    )

    op.create_table(
        "events",
        sa.Column("event_id", sa.String(length=26), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=True),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("actor_label", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "events_entity_type_entity_id_idx",
        "events",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "events_event_type_idx",
        "events",
        ["event_type"],
        unique=False,
    )

    op.create_table(
        "maintenance_status",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_canonical", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "role",
            sa.Enum("viewer", "editor", "admin", name="userrole", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("sso_provider", sa.String(length=100), nullable=True),
        sa.Column("sso_subject", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email_canonical"),
        sa.UniqueConstraint("sso_provider", "sso_subject"),
    )

    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=40), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("input_document_id", sa.String(length=26), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["input_document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "jobs_input_document_id_idx",
        "jobs",
        ["input_document_id"],
        unique=False,
    )

    with op.batch_alter_table("documents") as batch_op:
        batch_op.create_foreign_key(
            "documents_produced_by_job_id_fkey",
            "jobs",
            ["produced_by_job_id"],
            ["job_id"],
        )

    op.create_table(
        "api_keys",
        sa.Column("api_key_id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.String(length=32), nullable=True),
        sa.Column("last_seen_ip", sa.String(length=45), nullable=True),
        sa.Column("last_seen_user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("api_key_id"),
        sa.UniqueConstraint("token_prefix"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "api_keys_user_id_idx",
        "api_keys",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("api_keys_user_id_idx", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_table("users")

    op.drop_table("maintenance_status")

    op.drop_index("jobs_input_document_id_idx", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("events_event_type_idx", table_name="events")
    op.drop_index("events_entity_type_entity_id_idx", table_name="events")
    op.drop_table("events")

    op.drop_index("documents_produced_by_job_id_idx", table_name="documents")
    op.drop_table("documents")

    op.drop_index("configurations_document_type_active_idx", table_name="configurations")
    op.drop_table("configurations")
