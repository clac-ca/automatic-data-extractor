from __future__ import annotations

import os
import re
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.pool import NullPool

TEST_ENV_PREFIX = "ADE_TEST_"
_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class IsolatedTestDatabase:
    name: str
    database_url: URL
    admin_url: URL


def test_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(f"{TEST_ENV_PREFIX}{name}", default)


def require_test_env(name: str) -> str:
    value = test_env(name)
    if value and value.strip():
        return value
    raise RuntimeError(
        "Integration tests require "
        f"{TEST_ENV_PREFIX}{name}. Set it in the environment before running pytest."
    )


def _to_psycopg_driver(url: URL) -> URL:
    if url.drivername in {"postgresql", "postgres"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername.startswith("postgresql+"):
        return url.set(drivername="postgresql+psycopg")
    return url


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_VALUES


def _sanitize_database_name(name: str, *, fallback: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    return sanitized or fallback


def _assert_safe_database_name(name: str) -> None:
    allow_non_test = _is_truthy(test_env("ALLOW_NON_TEST_DATABASE", ""))
    if "test" not in name.lower() and not allow_non_test:
        raise RuntimeError(
            "Refusing to use non-test database name "
            f"{name!r}. Include 'test' in the name, or set "
            f"{TEST_ENV_PREFIX}ALLOW_NON_TEST_DATABASE=true to override."
        )


def _build_admin_url(url: URL) -> URL:
    admin_database = _sanitize_database_name(
        test_env("DATABASE_ADMIN_DB", "postgres") or "postgres",
        fallback="postgres",
    )
    return url.set(database=admin_database)


def resolve_isolated_test_database(*, default_prefix: str = "ade_test") -> IsolatedTestDatabase:
    base_url = make_url(require_test_env("DATABASE_URL"))
    explicit_name = test_env("DATABASE_NAME")
    if explicit_name:
        database_name = _sanitize_database_name(explicit_name, fallback=default_prefix)
    else:
        prefix = _sanitize_database_name(
            test_env("DATABASE_NAME_PREFIX", default_prefix) or default_prefix,
            fallback=default_prefix,
        )
        database_name = f"{prefix}_{uuid4().hex[:8]}"

    _assert_safe_database_name(database_name)
    isolated_url = _to_psycopg_driver(base_url.set(database=database_name))
    admin_url = _to_psycopg_driver(_build_admin_url(base_url))
    return IsolatedTestDatabase(
        name=database_name,
        database_url=isolated_url,
        admin_url=admin_url,
    )


def _build_engine(url: URL) -> Engine:
    return create_engine(
        url.render_as_string(hide_password=False),
        poolclass=NullPool,
        future=True,
    )


def create_isolated_test_database(database: IsolatedTestDatabase) -> None:
    engine = _build_engine(database.admin_url)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": database.name},
            ).scalar()
            if not exists:
                conn.exec_driver_sql(f'CREATE DATABASE "{database.name}"')
    finally:
        engine.dispose()


def drop_isolated_test_database(database: IsolatedTestDatabase) -> None:
    engine = _build_engine(database.admin_url)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name
                      AND pid <> pg_backend_pid();
                    """
                ),
                {"db_name": database.name},
            )
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database.name}"')
    finally:
        engine.dispose()


__all__ = [
    "IsolatedTestDatabase",
    "TEST_ENV_PREFIX",
    "create_isolated_test_database",
    "drop_isolated_test_database",
    "require_test_env",
    "resolve_isolated_test_database",
    "test_env",
]
