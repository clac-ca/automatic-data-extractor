"""FastAPI application factory for ADE."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth.router import router as auth_router
from .configurations.router import router as configurations_router
from .core.db.bootstrap import ensure_database_ready
from .core.logging import setup_logging
from .core.message_hub import MessageHub
from .core.middleware import register_middleware
from .core.settings import Settings, get_settings
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


def create_app(settings: Settings | None = None) -> FastAPI:
    """Instantiate and configure the FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings)

    if settings.api_docs_enabled:
        docs_url = settings.docs_url
        redoc_url = settings.redoc_url
        openapi_url = settings.openapi_url
    else:
        docs_url = None
        redoc_url = None
        openapi_url = None

    message_hub = MessageHub()
    task_queue = TaskQueue()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.message_hub = message_hub
        app.state.task_queue = task_queue
        await ensure_database_ready(settings)
        try:
            yield
        finally:
            hub_state = getattr(app.state, "message_hub", None)
            if isinstance(hub_state, MessageHub):
                hub_state.clear()
            queue_state = getattr(app.state, "task_queue", None)
            if isinstance(queue_state, TaskQueue):
                await queue_state.clear()
                queue_state.clear_subscribers()

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


app = create_app()


def start(host: str | None = None, port: int | None = None, reload: bool = False) -> None:
    """Run the ADE application using uvicorn."""

    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=host or settings.server_host,
        port=port or settings.server_port,
        reload=reload,
        factory=False,
    )
