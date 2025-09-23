"""Add canonical email column for users."""

from __future__ import annotations

from collections import defaultdict

from alembic import op
import sqlalchemy as sa
from email_validator import EmailNotValidError, validate_email


revision = "8b0c1d2e3f45"
down_revision = "a1b2c3d4e6f7"
branch_labels = None
depends_on = None


def _canonicalize_email(value: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        return ""
    try:
        result = validate_email(
            trimmed,
            allow_smtputf8=True,
            check_deliverability=False,
            globally_deliverable=False,
        )
    except EmailNotValidError as exc:
        raise RuntimeError(
            "Cannot canonicalise stored user email; invalid address detected"
        ) from exc

    local_part = result.local_part.casefold()
    domain = (result.ascii_domain or result.domain or "").casefold()
    canonical = f"{local_part}@{domain}" if domain else local_part
    if not canonical:
        raise RuntimeError("Canonical email could not be determined during migration")
    return canonical


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    needs_column = "email_canonical" not in existing_columns
    if needs_column:
        op.add_column(
            "users", sa.Column("email_canonical", sa.String(length=320), nullable=True)
        )
        inspector = sa.inspect(connection)

    users = sa.table(
        "users",
        sa.column("user_id", sa.String(length=26)),
        sa.column("email", sa.String(length=320)),
        sa.column("email_canonical", sa.String(length=320)),
    )

    results = connection.execute(sa.select(users.c.user_id, users.c.email)).all()
    grouped = defaultdict(list)
    for row in results:
        canonical = _canonicalize_email(row.email)
        if canonical:
            grouped[canonical].append(row.user_id)

    collisions = {key: ids for key, ids in grouped.items() if len(ids) > 1}
    if collisions:
        formatted = ", ".join(f"{key}: {ids}" for key, ids in collisions.items())
        msg = (
            "Cannot add users.email_canonical unique constraint; "
            f"duplicate canonical emails detected ({formatted})"
        )
        raise RuntimeError(msg)

    for row in results:
        canonical = _canonicalize_email(row.email)
        connection.execute(
            sa.update(users)
            .where(users.c.user_id == row.user_id)
            .values(email_canonical=canonical)
        )

    existing_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("users")
        if constraint.get("name")
    }

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "email_canonical",
            existing_type=sa.String(length=320),
            nullable=False,
        )
        if "uq_users_email_canonical" not in existing_constraints:
            batch_op.create_unique_constraint(
                "uq_users_email_canonical", ["email_canonical"]
            )
        if "uq_users_email" in existing_constraints:
            batch_op.drop_constraint("uq_users_email", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email_canonical", type_="unique")
        batch_op.drop_column("email_canonical")
        batch_op.create_unique_constraint("uq_users_email", ["email"])
