"""Drop environment lease columns (claimed_by, claim_expires_at)."""

from __future__ import annotations

from typing import Optional

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0007_drop_env_claims"
down_revision: Optional[str] = "0006_run_queue_notify"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_environments_claim_expires;")
    op.execute("ALTER TABLE environments DROP COLUMN IF EXISTS claimed_by;")
    op.execute("ALTER TABLE environments DROP COLUMN IF EXISTS claim_expires_at;")


def downgrade() -> None:  # pragma: no cover
    raise RuntimeError("Downgrade is not supported for this migration.")
