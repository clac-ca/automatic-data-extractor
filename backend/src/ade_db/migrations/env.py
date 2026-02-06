"""Alembic environment configuration (Postgres)."""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any, TypeGuard

from alembic import context

from ade_db.engine import DatabaseSettings as EngineDatabaseSettings
from ade_db.engine import build_engine
from ade_db.metadata import Base
from ade_db.settings import Settings

# Alembic Config object
config = context.config

# Keep Alembic logging optional (standard pattern)
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


# Import models so Base.metadata is populated
def _import_models() -> None:
    import ade_db.models  # noqa: F401


_import_models()
target_metadata = Base.metadata


def _is_database_settings(value: Any) -> TypeGuard[EngineDatabaseSettings]:
    required = (
        "database_url",
        "database_echo",
        "database_auth_mode",
        "database_sslrootcert",
        "database_pool_size",
        "database_max_overflow",
        "database_pool_timeout",
        "database_pool_recycle",
        "database_connect_timeout_seconds",
        "database_statement_timeout_ms",
    )
    return all(hasattr(value, key) for key in required)


def _build_settings() -> EngineDatabaseSettings:
    provided = config.attributes.get("settings")
    if _is_database_settings(provided):
        return provided
    override_url = config.get_main_option("sqlalchemy.url")
    if override_url:
        override_url = override_url.replace("%%", "%")
        return Settings(_env_file=None, database_url=override_url)
    return Settings()


def _normalized_url(settings: EngineDatabaseSettings) -> str:
    engine = build_engine(settings)
    try:
        return engine.url.render_as_string(hide_password=False)
    finally:
        engine.dispose()


def run_migrations_offline() -> None:
    settings = _build_settings()
    url = _normalized_url(settings)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # If a connection is passed in (rare but useful), use it
    existing_connection = config.attributes.get("connection")
    if existing_connection is not None:
        context.configure(
            connection=existing_connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    settings = _build_settings()
    engine = build_engine(settings)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
