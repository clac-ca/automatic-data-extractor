"""Alembic environment configuration for ADE."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from ade.settings import get_settings
from ade.db import metadata
from ade.db.engine import render_sync_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    override = os.getenv("ALEMBIC_DATABASE_URL")
    if override:
        return override

    settings = get_settings()
    return render_sync_url(settings.database_dsn)


def _should_render_as_batch(url: str) -> bool:
    try:
        backend = make_url(url).get_backend_name()
    except Exception:
        backend = "sqlite" if url.startswith("sqlite") else ""
    return backend == "sqlite"


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""

    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_should_render_as_batch(url),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a synchronous SQLAlchemy engine."""

    url = _database_url()
    existing_connection = config.attributes.get("connection")
    if existing_connection is not None:
        context.configure(
            connection=existing_connection,
            target_metadata=target_metadata,
            render_as_batch=_should_render_as_batch(url),
        )

        with context.begin_transaction():
            context.run_migrations()
        return

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=_should_render_as_batch(url),
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
