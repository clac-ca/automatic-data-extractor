from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text

from ade_db.engine import build_engine
from ade_db.migrations_runner import run_migrations
from ade_db.schema import metadata
from ade_worker.settings import Settings
from tests.integration_support import (
    IsolatedTestDatabase,
    create_isolated_test_database,
    drop_isolated_test_database,
    resolve_isolated_test_database,
    test_env,
)


def _build_test_settings(*, database_url: str) -> Settings:
    auth_mode = (test_env("DATABASE_AUTH_MODE") or "password").strip().lower()
    blob_container = test_env("BLOB_CONTAINER") or "ade-test"
    blob_connection_string = test_env("BLOB_CONNECTION_STRING")
    blob_account_url = test_env("BLOB_ACCOUNT_URL")
    if not blob_connection_string and not blob_account_url:
        blob_connection_string = "UseDevelopmentStorage=true"
    return Settings(
        _env_file=None,
        database_url=database_url,
        database_auth_mode=auth_mode,
        database_sslrootcert=test_env("DATABASE_SSLROOTCERT"),
        blob_container=blob_container,
        blob_connection_string=blob_connection_string,
        blob_account_url=blob_account_url,
    )


@pytest.fixture(scope="session")
def isolated_test_database() -> Iterator[IsolatedTestDatabase]:
    database = resolve_isolated_test_database(default_prefix="ade_worker_test")
    create_isolated_test_database(database)
    try:
        yield database
    finally:
        drop_isolated_test_database(database)


@pytest.fixture(scope="session")
def base_settings(isolated_test_database: IsolatedTestDatabase) -> Settings:
    return _build_test_settings(
        database_url=isolated_test_database.database_url.render_as_string(hide_password=False)
    )


@pytest.fixture(scope="session", autouse=True)
def _migrate_database(base_settings: Settings) -> None:
    run_migrations(base_settings)


@pytest.fixture(scope="session")
def engine(base_settings: Settings, _migrate_database: None):
    engine = build_engine(base_settings)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _truncate_tables(engine) -> Iterator[None]:
    with engine.begin() as conn:
        # Use unsorted table metadata; TRUNCATE ... CASCADE resolves FK dependency cycles.
        table_names = ", ".join(f'"{table.name}"' for table in metadata.tables.values())
        conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    yield
