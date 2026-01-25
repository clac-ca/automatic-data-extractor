from __future__ import annotations

import os
import re
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url

from ade_worker.db import build_engine
from ade_worker.schema import metadata, install_document_event_triggers
from ade_worker.settings import Settings


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(f"ADE_TEST_{name}") or os.getenv(f"ADE_{name}") or default


def _sanitize_db_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    return sanitized or "ade_worker_test"


def _resolve_test_database_name() -> str:
    explicit = os.getenv("ADE_TEST_SQL_DATABASE")
    if explicit:
        return _sanitize_db_name(explicit)
    prefix = os.getenv("ADE_TEST_SQL_DATABASE_PREFIX") or "ade_worker_test"
    prefix = _sanitize_db_name(prefix)
    suffix = uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def _build_test_settings() -> Settings:
    auth_mode = (os.getenv("ADE_TEST_DATABASE_AUTH_MODE") or "sql_password").strip().lower()
    return Settings(
        _env_file=None,
        sql_host=_env("SQL_HOST", "sql"),
        sql_port=int(_env("SQL_PORT", "1433") or "1433"),
        sql_user=_env("SQL_USER", "sa"),
        sql_password=_env("SQL_PASSWORD", "YourStrong!Passw0rd"),
        sql_database=_resolve_test_database_name(),
        sql_encrypt=_env("SQL_ENCRYPT", "optional"),
        sql_trust_server_certificate=_env("SQL_TRUST_SERVER_CERTIFICATE", "yes"),
        database_auth_mode=auth_mode,
    )


def _build_admin_settings(settings: Settings) -> Settings:
    url = make_url(settings.database_url).set(database="master")
    payload = settings.model_dump()
    payload["database_url_override"] = url.render_as_string(hide_password=False)
    return Settings.model_validate(payload)


def _create_database(settings: Settings) -> None:
    admin_settings = _build_admin_settings(settings)
    db_name = make_url(settings.database_url).database
    if not db_name:
        raise RuntimeError("Test database name was empty; check ADE_TEST_SQL_DATABASE settings.")
    engine = build_engine(admin_settings)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql(f"IF DB_ID(N'{db_name}') IS NULL CREATE DATABASE [{db_name}];")
    finally:
        engine.dispose()


def _drop_database(settings: Settings) -> None:
    admin_settings = _build_admin_settings(settings)
    db_name = make_url(settings.database_url).database
    if not db_name:
        return
    engine = build_engine(admin_settings)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql(
                f"""
                IF DB_ID(N'{db_name}') IS NOT NULL
                BEGIN
                    ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                    DROP DATABASE [{db_name}];
                END;
                """
            )
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def base_settings() -> Settings:
    return _build_test_settings()


@pytest.fixture(scope="session", autouse=True)
def _database_lifecycle(base_settings: Settings) -> Iterator[None]:
    _create_database(base_settings)
    yield
    _drop_database(base_settings)


@pytest.fixture(scope="session")
def engine(base_settings: Settings, _database_lifecycle: None):
    engine = build_engine(base_settings)
    metadata.create_all(engine)
    install_document_event_triggers(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _truncate_tables(engine) -> Iterator[None]:
    with engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())
    yield
