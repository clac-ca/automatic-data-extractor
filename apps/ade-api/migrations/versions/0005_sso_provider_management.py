"""Add managed_by and locked to SSO providers."""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0005_sso_provider_management"
down_revision: Optional[str] = "0004_sso_tables"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


SSO_PROVIDER_MANAGED_BY = sa.Enum(
    "db",
    "env",
    name="sso_provider_managed_by",
    native_enum=False,
    create_constraint=True,
    length=20,
)


def upgrade() -> None:
    op.add_column(
        "sso_providers",
        sa.Column(
            "managed_by",
            SSO_PROVIDER_MANAGED_BY,
            nullable=False,
            server_default="db",
        ),
    )
    op.add_column(
        "sso_providers",
        sa.Column(
            "locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute("UPDATE sso_providers SET managed_by = 'db' WHERE managed_by IS NULL")
    op.execute("UPDATE sso_providers SET locked = false WHERE locked IS NULL")


def downgrade() -> None:  # pragma: no cover
    op.drop_column("sso_providers", "locked")
    op.drop_column("sso_providers", "managed_by")

    bind = op.get_bind()
    SSO_PROVIDER_MANAGED_BY.drop(bind, checkfirst=False)
