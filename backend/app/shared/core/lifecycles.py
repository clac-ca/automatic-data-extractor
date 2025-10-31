"""FastAPI lifespan helpers for the ADE application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import Lifespan

from ..db.engine import ensure_database_ready
from ..db.session import get_sessionmaker
from ...features.roles.service import sync_permission_registry
from .config import DEFAULT_CONFIGS_SUBDIR, Settings, get_settings


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories required by the application."""

    resolved = settings or get_settings()

    data_dir = Path(resolved.storage_data_dir)
    documents_dir = getattr(resolved, "storage_documents_dir", None)
    configs_dir = getattr(resolved, "storage_configs_dir", None)
    jobs_dir = Path(resolved.storage_data_dir) / "jobs"

    targets: list[Path] = [data_dir]
    if documents_dir is not None:
        targets.append(Path(documents_dir))
    if configs_dir is not None:
        targets.append(Path(configs_dir))
    else:
        targets.append(data_dir / DEFAULT_CONFIGS_SUBDIR)
    targets.append(jobs_dir)

    for target in targets:
        target.mkdir(parents=True, exist_ok=True)


def create_application_lifespan(
    *,
    settings: Settings,
) -> Lifespan[FastAPI]:
    """Return the FastAPI lifespan handler used by the app factory."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ensure_runtime_dirs(settings)
        app.state.settings = settings
        await ensure_database_ready(settings)
        session_factory = get_sessionmaker(settings=settings)
        async with session_factory() as session:
            await sync_permission_registry(session=session)
        yield

    return lifespan


__all__ = ["create_application_lifespan", "ensure_runtime_dirs"]
