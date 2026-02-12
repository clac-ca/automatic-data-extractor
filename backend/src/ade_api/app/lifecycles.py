"""FastAPI lifespan helpers for the ADE application."""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import anyio.to_thread
from fastapi import FastAPI
from fastapi.routing import Lifespan
from sqlalchemy import text
from sqlalchemy.engine import make_url

from ade_api.common.logging import log_context
from ade_api.common.time import utc_now
from ade_api.core.auth.pipeline import dev_principal
from ade_api.core.security.hashing import hash_password
from ade_api.db import get_engine_from_app, get_session_factory_from_app, init_db, shutdown_db
from ade_api.features.admin_settings.service import (
    RuntimeSettingsInvariantError,
    RuntimeSettingsSchemaVersionError,
    RuntimeSettingsService,
)
from ade_api.features.documents.changes import purge_document_changes
from ade_api.features.documents.events import DocumentChangesHub
from ade_api.features.rbac import RbacService
from ade_api.features.sso.env_sync import sync_sso_providers_from_env
from ade_api.features.sso.group_sync import GroupSyncService
from ade_api.settings import Settings, get_settings
from ade_db.models import User
from ade_storage import (
    StorageError,
    ensure_storage_roots,
    get_storage_adapter,
    init_storage,
    shutdown_storage,
)

logger = logging.getLogger(__name__)
MAINTENANCE_INTERVAL_SECONDS = 24 * 60 * 60


def estimate_api_max_db_connections(settings: Settings) -> int:
    """Estimate API-side DB connection demand across worker processes."""

    process_count = int(settings.api_processes or 1)
    pool_capacity = int(settings.database_pool_size + settings.database_max_overflow)
    return process_count * pool_capacity


def _configure_threadpool_tokens(*, tokens: int) -> tuple[int, int]:
    limiter = anyio.to_thread.current_default_thread_limiter()
    previous = int(limiter.total_tokens)
    limiter.total_tokens = int(tokens)
    return previous, int(limiter.total_tokens)


def log_db_capacity_estimate(settings: Settings) -> int:
    estimated_connections = estimate_api_max_db_connections(settings)
    logger.info(
        "db.capacity.estimated",
        extra={
            "api_processes": int(settings.api_processes or 1),
            "database_pool_size": int(settings.database_pool_size),
            "database_max_overflow": int(settings.database_max_overflow),
            "estimated_max_connections": estimated_connections,
            "database_connection_budget": settings.database_connection_budget,
        },
    )
    if (
        settings.database_connection_budget is not None
        and estimated_connections > settings.database_connection_budget
    ):
        logger.warning(
            "db.capacity.budget_exceeded",
            extra={
                "estimated_max_connections": estimated_connections,
                "database_connection_budget": settings.database_connection_budget,
            },
        )
    return estimated_connections


async def _document_changes_maintenance_loop(maintain_fn: Callable[[], int]) -> None:
    while True:
        try:
            dropped = await asyncio.to_thread(maintain_fn)
            if dropped:
                logger.info(
                    "documents.changes.purged",
                    extra={"count": dropped},
                )
        except Exception:
            logger.exception("documents.changes.maintenance_failed")
        await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)


async def _group_sync_loop(*, sync_fn: Callable[[], None], interval_seconds: int) -> None:
    while True:
        try:
            await asyncio.to_thread(sync_fn)
        except Exception:
            logger.exception("sso.group_sync.loop_failed")
        await asyncio.sleep(interval_seconds)


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories required by the application."""

    resolved = settings or get_settings()

    ensure_storage_roots(resolved, extra=[Path(resolved.pip_cache_dir)])


def create_application_lifespan(
    *,
    settings: Settings,
) -> Lifespan[FastAPI]:
    """Return the FastAPI lifespan handler used by the app factory."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ensure_runtime_dirs(settings)
        app.state.settings = settings
        app.state.safe_mode = bool(settings.safe_mode)
        app.state.started_at = utc_now()
        previous_tokens, configured_tokens = _configure_threadpool_tokens(
            tokens=int(settings.api_threadpool_tokens)
        )
        logger.info(
            "api.threadpool.configured",
            extra={
                "tokens": configured_tokens,
                "previous_tokens": previous_tokens,
            },
        )
        log_db_capacity_estimate(settings)
        if settings.documents_upload_concurrency_limit:
            app.state.documents_upload_semaphore = threading.BoundedSemaphore(
                settings.documents_upload_concurrency_limit
            )
        else:
            app.state.documents_upload_semaphore = None

        logger.info(
            "ade_api.startup",
            extra=log_context(
                logging_level=settings.effective_api_log_level,
                safe_mode=bool(settings.safe_mode),
                auth_disabled=bool(settings.auth_disabled),
                version=settings.app_version,
            ),
        )
        if settings.safe_mode:
            logger.warning(
                "safe_mode.enabled",
                extra=log_context(safe_mode=True),
            )

        if settings.auth_disabled:
            logger.warning(
                "auth.disabled",
                extra=log_context(auth_disabled=True),
            )

        if not settings.database_url:
            raise RuntimeError("Database settings are required (set ADE_DATABASE_URL).")
        safe_url = make_url(str(settings.database_url)).render_as_string(hide_password=True)
        logger.info("db.init.start", extra={"database_url": safe_url})
        init_db(app, settings)
        logger.info("db.init.complete", extra={"database_url": safe_url})
        init_storage(app, settings)

        engine = get_engine_from_app(app)
        session_factory = get_session_factory_from_app(app)
        storage = get_storage_adapter(app)

        def _check_db_connection() -> None:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

        def _check_schema() -> None:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM alembic_version"))

        def _check_storage_connection() -> None:
            storage.check_connection()

        def _sync_rbac_registry() -> None:
            with session_factory() as session:
                service = RbacService(session=session)
                try:
                    with session.begin():
                        service.sync_registry()
                except Exception:
                    logger.warning("rbac.registry.sync.failed", exc_info=True)

        def _seed_dev_user() -> None:
            if not settings.auth_disabled:
                return

            principal = dev_principal(settings)
            with session_factory() as session:
                with session.begin():
                    user = session.get(User, principal.user_id)
                    if user is None:
                        alias = settings.auth_disabled_user_email or "developer@example.com"
                        user = User(
                            id=principal.user_id,
                            email=alias,
                            hashed_password=hash_password(secrets.token_urlsafe(32)),
                            display_name=settings.auth_disabled_user_name,
                            is_service_account=False,
                            is_active=True,
                            is_verified=True,
                        )
                        session.add(user)
                        session.flush()

                    service = RbacService(session=session)
                    admin_role = service.get_role_by_slug(slug="global-admin")
                    if admin_role is not None:
                        service.assign_role_if_missing(
                            user_id=principal.user_id,
                            role_id=admin_role.id,
                            workspace_id=None,
                        )

        def _sync_sso_env_providers() -> None:
            with session_factory() as session:
                with session.begin():
                    sync_sso_providers_from_env(session=session, settings=settings)

        def _sync_idp_groups() -> None:
            if not settings.auth_group_sync_enabled:
                return
            with session_factory() as session:
                with session.begin():
                    stats = GroupSyncService(session=session).run_once(settings=settings)
            logger.info(
                "sso.group_sync.complete",
                extra={
                    "users_upserted": stats.users_upserted,
                    "groups_upserted": stats.groups_upserted,
                    "memberships_added": stats.memberships_added,
                    "memberships_removed": stats.memberships_removed,
                },
            )

        def _assert_runtime_settings_schema() -> None:
            with session_factory() as session:
                with session.begin():
                    RuntimeSettingsService(
                        session=session,
                    ).assert_schema_supported()

        def _maintain_document_changes() -> int:
            with session_factory() as session:
                with session.begin():
                    return purge_document_changes(
                        session,
                        retention_days=settings.document_changes_retention_days,
                    )

        try:
            # Fail fast if the schema hasn't been migrated.
            try:
                await asyncio.to_thread(_check_db_connection)
            except Exception as exc:
                logger.error(
                    "db.connection.failed",
                    extra={"database_url": safe_url},
                    exc_info=True,
                )
                raise RuntimeError(
                    "Database is not reachable. Verify ADE_DATABASE_URL and credentials."
                ) from exc

            try:
                await asyncio.to_thread(_check_storage_connection)
            except StorageError as exc:
                logger.error(
                    "storage.connection.failed",
                    extra={"container": settings.blob_container},
                    exc_info=True,
                )
                raise RuntimeError(
                    "Blob storage is not reachable. Verify the container exists and "
                    "credentials are valid."
                ) from exc

            try:
                await asyncio.to_thread(_check_schema)
            except Exception as exc:
                logger.error(
                    "db.schema.missing",
                    extra={"database_url": safe_url},
                    exc_info=True,
                )
                raise RuntimeError(
                    "Database schema is not initialized. "
                    "Run `ade db migrate` before starting the API."
                ) from exc

            await asyncio.to_thread(_sync_rbac_registry)
            await asyncio.to_thread(_seed_dev_user)
            try:
                await asyncio.to_thread(_assert_runtime_settings_schema)
            except (
                RuntimeSettingsInvariantError,
                RuntimeSettingsSchemaVersionError,
            ) as exc:
                logger.error("runtime_settings.schema_unsupported", exc_info=True)
                raise RuntimeError(str(exc)) from exc
            await asyncio.to_thread(_sync_sso_env_providers)
            await asyncio.to_thread(_maintain_document_changes)
            if settings.auth_group_sync_enabled:
                await asyncio.to_thread(_sync_idp_groups)

            events_hub = DocumentChangesHub(settings=settings)
            events_hub.start(loop=asyncio.get_running_loop())
            app.state.document_changes_hub = events_hub
            maintenance_task = asyncio.create_task(
                _document_changes_maintenance_loop(_maintain_document_changes)
            )
            app.state.document_changes_maintenance_task = maintenance_task
            group_sync_task: asyncio.Task[None] | None = None
            if settings.auth_group_sync_enabled:
                group_sync_task = asyncio.create_task(
                    _group_sync_loop(
                        sync_fn=_sync_idp_groups,
                        interval_seconds=int(settings.auth_group_sync_interval_seconds),
                    )
                )
            app.state.group_sync_task = group_sync_task

            try:
                yield
            finally:
                maintenance_task.cancel()
                with suppress(asyncio.CancelledError):
                    await maintenance_task
                if group_sync_task is not None:
                    group_sync_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await group_sync_task
                events_hub.stop()
                app.state.document_changes_hub = None
                app.state.document_changes_maintenance_task = None
                app.state.group_sync_task = None
        finally:
            shutdown_storage(app)
            shutdown_db(app)

    return lifespan


__all__ = ["create_application_lifespan", "ensure_runtime_dirs"]
