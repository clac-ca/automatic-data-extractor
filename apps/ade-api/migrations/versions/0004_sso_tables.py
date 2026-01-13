"""Add SSO provider, identity, and auth state tables."""

from __future__ import annotations

import uuid
from typing import Any, Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import CHAR, TypeDecorator

# Revision identifiers, used by Alembic.
revision = "0004_sso_tables"
down_revision: Optional[str] = "0003_drop_document_event_request_fields"
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


SSO_PROVIDER_STATUS = sa.Enum(
    "active", "disabled", "deleted",
    name="sso_provider_status",
    native_enum=False,
    create_constraint=True,
    length=20,
)

SSO_PROVIDER_TYPE = sa.Enum(
    "oidc",
    name="sso_provider_type",
    native_enum=False,
    create_constraint=True,
    length=20,
)


def upgrade() -> None:
    op.create_table(
        "sso_providers",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("type", SSO_PROVIDER_TYPE, nullable=False, server_default="oidc"),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_enc", sa.Text(), nullable=False),
        sa.Column("status", SSO_PROVIDER_STATUS, nullable=False, server_default="disabled"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sso_providers_status", "sso_providers", ["status"], unique=False)
    op.create_index("ix_sso_providers_issuer", "sso_providers", ["issuer"], unique=False)

    op.create_table(
        "sso_provider_domains",
        sa.Column(
            "provider_id",
            sa.String(length=64),
            sa.ForeignKey("sso_providers.id", ondelete="NO ACTION"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("domain", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("domain", name="uq_sso_provider_domains_domain"),
    )
    op.create_index(
        "ix_sso_provider_domains_domain",
        "sso_provider_domains",
        ["domain"],
        unique=False,
    )
    op.create_index(
        "ix_sso_provider_domains_provider",
        "sso_provider_domains",
        ["provider_id"],
        unique=False,
    )
    op.create_table(
        "sso_identities",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "provider_id",
            sa.String(length=64),
            sa.ForeignKey("sso_providers.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider_id", "subject", name="uq_sso_identities_provider_subject"),
        sa.UniqueConstraint("provider_id", "user_id", name="uq_sso_identities_provider_user"),
    )
    op.create_index("ix_sso_identities_user", "sso_identities", ["user_id"], unique=False)
    op.create_index(
        "ix_sso_identities_provider_subject",
        "sso_identities",
        ["provider_id", "subject"],
        unique=False,
    )
    op.create_table(
        "sso_auth_states",
        sa.Column("state", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column(
            "provider_id",
            sa.String(length=64),
            sa.ForeignKey("sso_providers.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("nonce", sa.String(length=255), nullable=False),
        sa.Column("pkce_verifier", sa.String(length=255), nullable=False),
        sa.Column("return_to", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sso_auth_states_expires", "sso_auth_states", ["expires_at"], unique=False)
    op.create_index("ix_sso_auth_states_provider", "sso_auth_states", ["provider_id"], unique=False)


def downgrade() -> None:  # pragma: no cover
    op.drop_index("ix_sso_auth_states_provider", table_name="sso_auth_states")
    op.drop_index("ix_sso_auth_states_expires", table_name="sso_auth_states")
    op.drop_table("sso_auth_states")

    op.drop_index("ix_sso_identities_provider_subject", table_name="sso_identities")
    op.drop_index("ix_sso_identities_user", table_name="sso_identities")
    op.drop_table("sso_identities")

    op.drop_index("ix_sso_provider_domains_provider", table_name="sso_provider_domains")
    op.drop_index("ix_sso_provider_domains_domain", table_name="sso_provider_domains")
    op.drop_table("sso_provider_domains")

    op.drop_index("ix_sso_providers_issuer", table_name="sso_providers")
    op.drop_index("ix_sso_providers_status", table_name="sso_providers")
    op.drop_table("sso_providers")

    bind = op.get_bind()
    SSO_PROVIDER_STATUS.drop(bind, checkfirst=False)
    SSO_PROVIDER_TYPE.drop(bind, checkfirst=False)
