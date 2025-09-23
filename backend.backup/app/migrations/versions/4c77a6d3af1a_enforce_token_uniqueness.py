"""Enforce uniqueness for tokens and emails."""

from __future__ import annotations

from collections.abc import Sequence


from alembic import op
import sqlalchemy as sa


revision = "4c77a6d3af1a"
down_revision = "07076d8a6413"
branch_labels = None
depends_on = None


def _check_for_duplicates(connection, table: str, column: str) -> None:
    table_obj = sa.table(table, sa.column(column))
    column_ref = table_obj.c[column]
    stmt = (
        sa.select(column_ref)
        .where(column_ref.is_not(None))
        .group_by(column_ref)
        .having(sa.func.count() > 1)
    )
    result = connection.execute(stmt).first()
    if result is not None:
        value = result[0]
        raise RuntimeError(
            f"Duplicate values detected for {table}.{column}: {value!r}. "
            "Resolve the duplicates before applying this migration."
        )


def _unique_exists(inspector: sa.engine.reflection.Inspector, table: str, columns: Sequence[str]) -> bool:
    target = tuple(columns)
    for constraint in inspector.get_unique_constraints(table):
        existing = tuple(constraint.get("column_names", ()))
        if existing == target:
            return True
    return False


def _create_unique_constraint(
    connection: sa.engine.Connection,
    inspector: sa.engine.reflection.Inspector,
    table: str,
    name: str,
    columns: Sequence[str],
) -> None:
    if _unique_exists(inspector, table, columns):
        return

    if connection.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_unique_constraint(name, columns)
    else:
        op.create_unique_constraint(name, table, columns)


def _drop_unique_constraint(
    connection: sa.engine.Connection,
    inspector: sa.engine.reflection.Inspector,
    table: str,
    name: str,
    columns: Sequence[str],
) -> None:
    match = None
    for constraint in inspector.get_unique_constraints(table):
        if constraint.get("name") == name:
            match = constraint
            break

    if match is None:
        return

    if connection.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(name, type_="unique")
    else:
        op.drop_constraint(name, table, type_="unique")


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    _check_for_duplicates(connection, "users", "email")
    _check_for_duplicates(connection, "user_sessions", "token_hash")
    _check_for_duplicates(connection, "api_keys", "token_hash")
    _check_for_duplicates(connection, "api_keys", "token_prefix")

    _create_unique_constraint(
        connection,
        inspector,
        "user_sessions",
        "uq_user_sessions_token_hash",
        ["token_hash"],
    )
    _create_unique_constraint(
        connection,
        inspector,
        "api_keys",
        "uq_api_keys_token_hash",
        ["token_hash"],
    )
    _create_unique_constraint(
        connection,
        inspector,
        "api_keys",
        "uq_api_keys_token_prefix",
        ["token_prefix"],
    )
    _create_unique_constraint(
        connection,
        inspector,
        "users",
        "uq_users_email",
        ["email"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    _drop_unique_constraint(
        connection,
        inspector,
        "api_keys",
        "uq_api_keys_token_prefix",
        ["token_prefix"],
    )
    _drop_unique_constraint(
        connection,
        inspector,
        "api_keys",
        "uq_api_keys_token_hash",
        ["token_hash"],
    )
    _drop_unique_constraint(
        connection,
        inspector,
        "user_sessions",
        "uq_user_sessions_token_hash",
        ["token_hash"],
    )
    _drop_unique_constraint(
        connection,
        inspector,
        "users",
        "uq_users_email",
        ["email"],
    )
