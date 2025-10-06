"""Initial ADE schema with workspace ownership."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    _create_users()
    _create_workspaces()
    _create_workspace_memberships()
    _create_api_keys()
    _create_configurations()
    _create_documents()
    _create_jobs()
    _create_system_settings()


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("jobs")
    op.drop_table("documents")
    op.drop_table("configurations")
    op.drop_table("api_keys")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
    op.drop_table("users")


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=26), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_canonical", sa.String(length=320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_service_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "role",
            sa.Enum("admin", "member", name="userrole", native_enum=False, length=20),
            nullable=False,
            server_default="member",
        ),
        sa.Column("sso_provider", sa.String(length=100), nullable=True),
        sa.Column("sso_subject", sa.String(length=255), nullable=True),
        sa.Column("last_login_at", sa.String(length=32), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.UniqueConstraint("sso_provider", "sso_subject"),
    )


def _create_workspaces() -> None:
    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )


def _create_workspace_memberships() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column("workspace_membership_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "member",
                "owner",
                name="workspacerole",
                native_enum=False,
                length=20,
            ),
            nullable=False,
            server_default="member",
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "workspace_id"),
    )
    op.create_index(
        "workspace_memberships_user_id_idx",
        "workspace_memberships",
        ["user_id"],
        unique=False,
    )


def _create_api_keys() -> None:
    op.create_table(
        "api_keys",
        sa.Column("api_key_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.String(length=32), nullable=True),
        sa.Column("last_seen_at", sa.String(length=32), nullable=True),
        sa.Column("last_seen_ip", sa.String(length=45), nullable=True),
        sa.Column("last_seen_user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
    )
    op.create_index("api_keys_user_id_idx", "api_keys", ["user_id"], unique=False)


def _create_configurations() -> None:
    op.create_table(
        "configurations",
        sa.Column("configuration_id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activated_at", sa.String(length=32), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("workspace_id", "document_type", "version"),
    )
    op.create_index(
        "configurations_workspace_active_idx",
        "configurations",
        ["workspace_id", "document_type"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
    )


def _create_documents() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(length=26), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_uri", sa.String(length=512), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("deleted_at", sa.String(length=32), nullable=True),
        sa.Column("deleted_by", sa.String(length=100), nullable=True),
        sa.Column("delete_reason", sa.String(length=1024), nullable=True),
        sa.Column("produced_by_job_id", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("documents_workspace_id_idx", "documents", ["workspace_id"], unique=False)
    op.create_index(
        "documents_produced_by_job_id_idx",
        "documents",
        ["produced_by_job_id"],
        unique=False,
    )


def _create_jobs() -> None:
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=40), primary_key=True),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("configuration_id", sa.String(length=26), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("input_document_id", sa.String(length=26), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("logs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["input_document_id"],
            ["documents.document_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index("jobs_workspace_id_idx", "jobs", ["workspace_id"], unique=False)
    op.create_index("jobs_input_document_id_idx", "jobs", ["input_document_id"], unique=False)

def _create_system_settings() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )
