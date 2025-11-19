"""FastAPI lifespan helpers for the ADE application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import Lifespan

from ade_api.settings import Settings, get_settings

from ...features.roles.service import sync_permission_registry
from ..db.engine import ensure_database_ready
from ..db.session import get_sessionmaker


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories required by the application."""

    resolved = settings or get_settings()

    targets: set[Path] = set()
    for attribute in ("documents_dir", "configs_dir", "venvs_dir", "jobs_dir", "pip_cache_dir"):
        candidate = getattr(resolved, attribute, None)
        if candidate is not None:
            targets.add(Path(candidate))

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
        app.state.safe_mode = bool(settings.safe_mode)
        await ensure_database_ready(settings)
        session_factory = get_sessionmaker(settings=settings)
        async with session_factory() as session:
            await sync_permission_registry(session=session)
        yield

    return lifespan


__all__ = ["create_application_lifespan", "ensure_runtime_dirs"]
