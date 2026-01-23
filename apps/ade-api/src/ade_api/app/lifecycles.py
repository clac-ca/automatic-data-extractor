"""FastAPI lifespan helpers for the ADE application."""

from __future__ import annotations

import asyncio
import threading
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import Lifespan
from sqlalchemy import text
from sqlalchemy.engine import make_url

from ade_api.db import get_engine, get_sessionmaker_from_app, init_db, shutdown_db
from ade_api.features.documents.change_feed import run_document_events_pruner
from ade_api.features.rbac import RbacService
from ade_api.features.sso.env_sync import sync_sso_providers_from_env
from ade_api.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories required by the application."""

    resolved = settings or get_settings()

    targets: set[Path] = {
        Path(resolved.data_dir),
        Path(resolved.workspaces_dir),
        Path(resolved.venvs_dir),
        Path(resolved.pip_cache_dir),
        Path(resolved.data_dir) / "db",
    }

    for target in targets:
        target.mkdir(parents=True, exist_ok=True)

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
        if settings.documents_upload_concurrency_limit:
            app.state.documents_upload_semaphore = threading.BoundedSemaphore(
                settings.documents_upload_concurrency_limit
            )
        else:
            app.state.documents_upload_semaphore = None
        if not settings.database_url:
            raise RuntimeError("Database settings are required (set ADE_SQL_*).")
        safe_url = make_url(settings.database_url).render_as_string(hide_password=True)
        logger.info("db.init.start", extra={"database_url": safe_url})
        init_db(app, settings)
        logger.info("db.init.complete", extra={"database_url": safe_url})

        engine = get_engine(app)
        session_factory = get_sessionmaker_from_app(app)

        def _check_schema() -> None:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM alembic_version"))

        def _sync_rbac_registry() -> None:
            with session_factory() as session:
                service = RbacService(session=session)
                try:
                    with session.begin():
                        service.sync_registry()
                except Exception:
                    logger.warning("rbac.registry.sync.failed", exc_info=True)

        def _sync_sso_env_providers() -> None:
            with session_factory() as session:
                with session.begin():
                    sync_sso_providers_from_env(session=session, settings=settings)

        try:
            # Fail fast if the schema hasn't been migrated.
            try:
                await asyncio.to_thread(_check_schema)
            except Exception as exc:
                logger.error(
                    "db.schema.missing",
                    extra={"database_url": safe_url},
                    exc_info=True,
                )
                raise RuntimeError(
                    "Database schema is not initialized. Run `ade migrate` before starting the API."
                ) from exc

            await asyncio.to_thread(_sync_rbac_registry)
            await asyncio.to_thread(_sync_sso_env_providers)

            pruner_stop = asyncio.Event()
            pruner_task = asyncio.create_task(
                run_document_events_pruner(
                    settings=settings,
                    stop_event=pruner_stop,
                    session_factory=session_factory,
                )
            )

            try:
                yield
            finally:
                pruner_stop.set()
                pruner_task.cancel()
                with suppress(asyncio.CancelledError):
                    await pruner_task
        finally:
            shutdown_db(app)

    return lifespan


__all__ = ["create_application_lifespan", "ensure_runtime_dirs"]
