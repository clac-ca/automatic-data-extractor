"""ADE FastAPI application entry point."""

from __future__ import annotations

import os
import shutil
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Mapping
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth.router import router as auth_router
from .configurations.router import router as configurations_router
from .core.db.bootstrap import ensure_database_ready
from .core.logging import setup_logging
from .core.message_hub import MessageHub
from .core.middleware import register_middleware
from .settings import Settings, get_settings
from .core.task_queue import TaskQueue
from .documents.router import router as documents_router
from .health.router import router as health_router
from .jobs.router import router as jobs_router
from .results.router import router as results_router
from .users.router import router as users_router
from .workspaces.router import router as workspaces_router

STATIC_DIR = Path(__file__).resolve().parent / "static"
SPA_INDEX = STATIC_DIR / "index.html"
API_PREFIX = "/api"
DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
FRONTEND_BUILD_DIRNAME = "dist"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Return a configured FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings)

    docs_url = settings.docs_url if settings.api_docs_enabled else None
    redoc_url = settings.redoc_url if settings.api_docs_enabled else None
    openapi_url = settings.openapi_url if settings.api_docs_enabled else None

    message_hub = MessageHub()
    task_queue = TaskQueue()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.message_hub = message_hub
        app.state.task_queue = task_queue
        await ensure_database_ready(settings)
        try:
            yield
        finally:
            message_hub.clear()
            await task_queue.clear()
            task_queue.clear_subscribers()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.message_hub = message_hub
    app.state.task_queue = task_queue

    register_middleware(app)
    _mount_static(app)
    _register_routes(app)
    return app


def start(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    *,
    rebuild_frontend: bool = False,
    frontend_dir: str | Path | None = None,
    npm_command: str | None = None,
    env_overrides: Mapping[str, str] | None = None,
) -> None:
    """Start uvicorn using the ADE application."""

    settings = get_settings()
    bind_host = host or settings.server_host
    bind_port = port or settings.server_port

    for key, value in (env_overrides or {}).items():
        os.environ[key] = value

    os.environ.setdefault("ADE_SERVER_HOST", bind_host)
    os.environ.setdefault("ADE_SERVER_PORT", str(bind_port))
    os.environ.setdefault("ADE_SERVER_PUBLIC_URL", f"http://{bind_host}:{bind_port}")

    if rebuild_frontend:
        build_frontend_assets(
            frontend_dir=frontend_dir,
            npm_command=npm_command,
            env=os.environ,
        )
        print("Frontend: rebuilt and synced to app/static")
    else:
        print("Frontend: serving existing assets from app/static")

    print("ADE application server")
    print("---------------------")
    print(f"Listening on http://{bind_host}:{bind_port}")
    print(f"Reload: {'enabled' if reload else 'disabled'}\n")

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        factory=False,
    )


def build_frontend_assets(
    *,
    frontend_dir: str | Path | None = None,
    npm_command: str | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    source = Path(frontend_dir) if frontend_dir is not None else DEFAULT_FRONTEND_DIR
    source = source.expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise ValueError(f"Frontend directory not found at {source}")

    environment = dict(env or os.environ)
    npm = npm_command or ("npm.cmd" if os.name == "nt" else "npm")

    if not (source / "node_modules").exists():
        print("Installing frontend dependencies (npm install)...")
        subprocess.run([npm, "install"], cwd=source, env=environment, check=True)

    print("Building frontend bundle...")
    subprocess.run([npm, "run", "build"], cwd=source, env=environment, check=True)

    sync_frontend_assets(source / FRONTEND_BUILD_DIRNAME)


def sync_frontend_assets(
    dist_dir: str | Path,
    static_dir: str | Path | None = None,
) -> None:
    build_dir = Path(dist_dir).expanduser().resolve()
    if not build_dir.exists() or not build_dir.is_dir():
        raise ValueError(f"Frontend build output not found at {build_dir}")

    target = Path(static_dir).expanduser().resolve() if static_dir else STATIC_DIR
    target.mkdir(parents=True, exist_ok=True)

    for entry in target.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()

    shutil.copytree(build_dir, target, dirs_exist_ok=True)


def _mount_static(app: FastAPI) -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def read_spa_root() -> FileResponse:
        if not SPA_INDEX.exists():
            raise HTTPException(status_code=404, detail="SPA build not found")
        return FileResponse(SPA_INDEX)


def _register_routes(app: FastAPI) -> None:
    app.include_router(health_router, prefix=f"{API_PREFIX}/health", tags=["health"])
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(users_router, prefix=API_PREFIX)
    app.include_router(workspaces_router, prefix=API_PREFIX)
    app.include_router(configurations_router, prefix=API_PREFIX)
    app.include_router(documents_router, prefix=API_PREFIX)
    app.include_router(jobs_router, prefix=API_PREFIX)
    app.include_router(results_router, prefix=API_PREFIX)


app = create_app()

__all__ = [
    "API_PREFIX",
    "DEFAULT_FRONTEND_DIR",
    "FRONTEND_BUILD_DIRNAME",
    "STATIC_DIR",
    "app",
    "build_frontend_assets",
    "create_app",
    "start",
    "sync_frontend_assets",
]
