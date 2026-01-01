"""Alembic environment configuration (SQLite + SQL Server only)."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from ade_api.db.base import metadata
from ade_api.db.database import DatabaseConfig, attach_managed_identity, build_sync_url

# Alembic Config object
config = context.config

# Keep Alembic logging optional (standard pattern)
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


# Import models so Base.metadata is populated
def _import_models() -> None:
    import ade_api.models  # noqa: F401


_import_models()
target_metadata = metadata


def _get_url() -> str:
    # 1) alembic.ini sqlalchemy.url
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    # 2) explicit override
    override = os.getenv("ALEMBIC_DATABASE_URL")
    if override:
        return override

    # 3) ADE_DATABASE_URL from env (sync URL expected)
    cfg = DatabaseConfig.from_env()
    return build_sync_url(cfg)


def _is_sqlite(url: str) -> bool:
    try:
        return make_url(url).get_backend_name() == "sqlite"
    except Exception:
        return url.startswith("sqlite")


def _use_managed_identity(url: str) -> bool:
    cfg = DatabaseConfig.from_env()
    try:
        backend = make_url(url).get_backend_name()
    except Exception:
        backend = "sqlite" if url.startswith("sqlite") else ""
    return cfg.auth_mode == "managed_identity" and backend == "mssql"


def run_migrations_offline() -> None:
    url = _get_url()
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
    url = _get_url()

    # If a connection is passed in (rare but useful), use it
    existing_connection = config.attributes.get("connection")
    if existing_connection is not None:
        context.configure(
            connection=existing_connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(url),
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    if _use_managed_identity(url):
        cfg = DatabaseConfig.from_env()
        attach_managed_identity(connectable, client_id=cfg.managed_identity_client_id)

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=_is_sqlite(url),
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
