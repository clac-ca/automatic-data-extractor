"""FastAPI lifespan helpers for the ADE application."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import Lifespan

from ade_api.settings import Settings, get_settings

from ...features.roles import RbacService
from ..db.engine import ensure_database_ready
from ..db.session import get_sessionmaker

logger = logging.getLogger(__name__)


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories required by the application."""

    resolved = settings or get_settings()

    targets: set[Path] = set()
    for attribute in (
        "workspaces_dir",
        "documents_dir",
        "configs_dir",
        "venvs_dir",
        "runs_dir",
        "pip_cache_dir",
    ):
        candidate = getattr(resolved, attribute, None)
        if candidate is not None:
            targets.add(Path(candidate))

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
        raise RuntimeError(f"ADE_VENVS_DIR is not writable: {venvs_dir} ({exc})") from exc

    if _looks_like_network_share(venvs_dir):
        logger.warning(
            "venvs_dir.network_like",
            extra={
                "venvs_dir": str(venvs_dir),
                "message": "ADE_VENVS_DIR appears to be on a network/SMB mount; "
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
        await ensure_database_ready(settings)
        session_factory = get_sessionmaker(settings=settings)
        async with session_factory() as session:
            rbac = RbacService(session=session)
            await rbac.sync_registry()
        yield

    return lifespan


__all__ = ["create_application_lifespan", "ensure_runtime_dirs"]
