"""FastAPI lifespan helpers for the ADE application."""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import Lifespan
from sqlalchemy import text
from sqlalchemy.engine import make_url

from ade_api.common.logging import log_context
from ade_api.common.time import utc_now
from ade_api.core.auth.pipeline import dev_principal
from ade_api.core.security.hashing import hash_password
from ade_api.db import get_engine_from_app, get_session_factory_from_app, init_db, shutdown_db
from ade_api.features.documents.changes import purge_document_changes
from ade_api.features.documents.events import DocumentChangesHub
from ade_api.features.rbac import RbacService
from ade_api.features.sso.env_sync import sync_sso_providers_from_env
from ade_storage import (
    StorageError,
    ensure_storage_roots,
    get_storage_adapter,
    init_storage,
    shutdown_storage,
)
from ade_api.settings import Settings, get_settings
from ade_db.models import User

logger = logging.getLogger(__name__)
MAINTENANCE_INTERVAL_SECONDS = 24 * 60 * 60


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


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories required by the application."""

    resolved = settings or get_settings()

    ensure_storage_roots(resolved, extra=[Path(resolved.pip_cache_dir)])

    _validate_venvs_dir(Path(resolved.venvs_dir))


def _validate_venvs_dir(venvs_dir: Path) -> None:
    """Ensure the configured venvs directory is writable and likely local."""

    venvs_dir.mkdir(parents=True, exist_ok=True)
    marker = venvs_dir / ".ade-venv-writecheck"

    try:
        marker.write_text("ok", encoding="utf-8")
        marker.unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover - defensive guard for startup
        raise RuntimeError(f"ADE_DATA_DIR/venvs is not writable: {venvs_dir} ({exc})") from exc

    if _looks_like_network_share(venvs_dir):
        logger.warning(
            "venvs_dir.network_like",
            extra={
                "venvs_dir": str(venvs_dir),
                "detail": "ADE_DATA_DIR/venvs appears to be on a network/SMB mount; "
                "venvs must live on local storage",
            },
        )


def _looks_like_network_share(path: Path) -> bool:
    """Best-effort detection of network mounts (SMB/NFS/UNC)."""

    as_posix = path.as_posix()
    if as_posix.startswith("//") or as_posix.startswith("\\\\"):
        return True

    mounts_path = Path("/proc/mounts")
    if mounts_path.exists():
        try:
            resolved = path.resolve()
            best_match: tuple[int, str] | None = None
            with mounts_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) < 3:
                        continue
                    mount_point, fs_type = parts[1], parts[2]
                    if fs_type.lower() in {"cifs", "smbfs", "nfs", "nfs4"}:
                        if str(resolved).startswith(mount_point.rstrip("/") + "/"):
                            depth = mount_point.count("/")
                            if best_match is None or depth > best_match[0]:
                                best_match = (depth, fs_type)
            if best_match:
                return True
        except OSError:
            return False

    # Windows UNC paths handled above; as a fallback, flag paths under /mnt/ or /media/
    # which are often backed by remote filesystems in containerized environments.
    parts = {part.lower() for part in path.parts}
    return "mnt" in parts or "media" in parts


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
        if settings.documents_upload_concurrency_limit:
            app.state.documents_upload_semaphore = threading.BoundedSemaphore(
                settings.documents_upload_concurrency_limit
            )
        else:
            app.state.documents_upload_semaphore = None

        logger.info(
            "ade_api.startup",
            extra=log_context(
                logging_level=settings.log_level,
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
                            is_superuser=True,
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
                    "Database schema is not initialized. Run `ade db migrate` before starting the API."
                ) from exc

            await asyncio.to_thread(_sync_rbac_registry)
            await asyncio.to_thread(_seed_dev_user)
            await asyncio.to_thread(_sync_sso_env_providers)
            await asyncio.to_thread(_maintain_document_changes)

            events_hub = DocumentChangesHub(settings=settings)
            events_hub.start(loop=asyncio.get_running_loop())
            app.state.document_changes_hub = events_hub
            maintenance_task = asyncio.create_task(_document_changes_maintenance_loop(_maintain_document_changes))
            app.state.document_changes_maintenance_task = maintenance_task

            try:
                yield
            finally:
                maintenance_task.cancel()
                with suppress(asyncio.CancelledError):
                    await maintenance_task
                events_hub.stop()
                app.state.document_changes_hub = None
                app.state.document_changes_maintenance_task = None
        finally:
            shutdown_storage(app)
            shutdown_db(app)

    return lifespan


__all__ = ["create_application_lifespan", "ensure_runtime_dirs"]
