from __future__ import annotations

import os
import re
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from ade_worker.db import build_engine
from ade_worker.schema import metadata
from ade_worker.settings import DEFAULT_DATABASE_AUTH_MODE, DEFAULT_DATABASE_URL, Settings


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(f"ADE_TEST_{name}") or os.getenv(f"ADE_{name}") or default


def _sanitize_db_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    return sanitized or "ade_worker_test"


def _resolve_test_database_name() -> str:
    explicit = os.getenv("ADE_TEST_DATABASE_NAME")
    if explicit:
        return _sanitize_db_name(explicit)
    prefix = os.getenv("ADE_TEST_DATABASE_NAME_PREFIX") or "ade_worker_test"
    prefix = _sanitize_db_name(prefix)
    suffix = uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def _build_test_settings() -> Settings:
    auth_mode = (_env("DATABASE_AUTH_MODE", DEFAULT_DATABASE_AUTH_MODE) or "password").strip().lower()
    base_url = _env("DATABASE_URL", DEFAULT_DATABASE_URL) or DEFAULT_DATABASE_URL
    url = make_url(base_url).set(database=_resolve_test_database_name())
    return Settings(
        _env_file=None,
        database_url=url.render_as_string(hide_password=False),
        database_auth_mode=auth_mode,
        database_sslrootcert=_env("DATABASE_SSLROOTCERT"),
        storage_backend="filesystem",
    )


def _build_admin_settings(settings: Settings) -> Settings:
    url = make_url(settings.database_url).set(database="postgres")
    payload = settings.model_dump()
    payload["database_url"] = url.render_as_string(hide_password=False)
    return Settings.model_validate(payload)


def _create_database(settings: Settings) -> None:
    admin_settings = _build_admin_settings(settings)
    db_name = make_url(settings.database_url).database
    if not db_name:
        raise RuntimeError("Test database name was empty; check ADE_TEST_DATABASE_NAME settings.")
    engine = build_engine(admin_settings)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            ).scalar()
            if not exists:
                conn.exec_driver_sql(f'CREATE DATABASE "{db_name}";')
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
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name
                      AND pid <> pg_backend_pid();
                    """
                ),
                {"db_name": db_name},
            )
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{db_name}";')
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
