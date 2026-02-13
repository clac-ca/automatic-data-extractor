"""Hard-cut invitation lifecycle storage to derived expiration semantics.

Adds direct workspace scoping, rewrites persisted expired rows back to pending,
and tightens persisted statuses so expiration is API-derived only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision = "0003_invitation_lifecycle_status"
down_revision = "0002_access_model_hard_cutover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("workspace_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_invitations_workspace_id_workspaces"),
        "invitations",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="NO ACTION",
    )

    op.execute(
        """
        UPDATE invitations
        SET workspace_id = (metadata->>'workspaceId')::uuid
        WHERE metadata IS NOT NULL
          AND metadata->>'workspaceId' IS NOT NULL
          AND (metadata->>'workspaceId') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        """
    )

    op.execute(
        """
        UPDATE invitations
        SET status = 'pending',
            expires_at = COALESCE(expires_at, created_at)
        WHERE status = 'expired'
        """
    )

    op.drop_constraint("ck_invitations_status", "invitations", type_="check")
    op.create_check_constraint(
        "ck_invitations_status",
        "invitations",
        "status in ('pending', 'accepted', 'cancelled')",
    )

    op.create_index(
        "ix_invitations_workspace_status_expires",
        "invitations",
        ["workspace_id", "status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_invitations_workspace_created_id",
        "invitations",
        ["workspace_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
