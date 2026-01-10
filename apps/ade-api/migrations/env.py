"""Alembic environment configuration (SQLite + SQL Server only)."""

from __future__ import annotations

import os
from dataclasses import replace
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import make_url

from ade_api.db import Base, DatabaseSettings, build_engine

# Alembic Config object
config = context.config

# Keep Alembic logging optional (standard pattern)
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


# Import models so Base.metadata is populated
def _import_models() -> None:
    import ade_api.models  # noqa: F401


_import_models()
target_metadata = Base.metadata


def _get_url_override() -> str | None:
    # 1) alembic.ini sqlalchemy.url
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    # 2) explicit override
    override = os.getenv("ALEMBIC_DATABASE_URL")
    if override:
        return override

    # 3) fall back to ADE_DATABASE_URL via DatabaseSettings.from_env()
    return None


def _build_settings(url_override: str | None) -> DatabaseSettings:
    settings = DatabaseSettings.from_env()
    if url_override:
        settings = replace(settings, url=url_override)
    return settings


def _normalized_url(settings: DatabaseSettings) -> str:
    engine = build_engine(settings)
    try:
        return engine.url.render_as_string(hide_password=False)
    finally:
        engine.dispose()


def _is_sqlite(url: str) -> bool:
    try:
        return make_url(url).get_backend_name() == "sqlite"
    except Exception:
        return url.startswith("sqlite")


def run_migrations_offline() -> None:
    settings = _build_settings(_get_url_override())
    url = _normalized_url(settings)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url_override = _get_url_override()

    # If a connection is passed in (rare but useful), use it
    existing_connection = config.attributes.get("connection")
    if existing_connection is not None:
        context.configure(
            connection=existing_connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(
                existing_connection.engine.url.render_as_string(hide_password=False)
            ),
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    settings = _build_settings(url_override)
    engine = build_engine(settings)
    try:
        url = engine.url.render_as_string(hide_password=False)
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=_is_sqlite(url),
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
