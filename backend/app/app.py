"""ADE FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.errors import register_exception_handlers
from .features.auth.dependencies import configure_auth_dependencies
from .features.jobs.tasks import register_job_tasks
from .lifecycles import create_application_lifespan
from .platform.config import Settings, get_settings
from .platform.logging import setup_logging
from .platform.middleware import register_middleware
from .workers.task_queue import TaskQueue
from .v1.router import router as api_router

WEB_DIR = Path(__file__).resolve().parent / "web"
WEB_STATIC_DIR = WEB_DIR / "static"
SPA_INDEX = WEB_STATIC_DIR / "index.html"
API_PREFIX = "/api"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Return a configured FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings)

    docs_url = settings.docs_url if settings.api_docs_enabled else None
    redoc_url = settings.redoc_url if settings.api_docs_enabled else None
    openapi_url = settings.openapi_url if settings.api_docs_enabled else None

    task_queue = TaskQueue()
    register_job_tasks(task_queue)
    lifespan = create_application_lifespan(
        settings=settings,
        task_queue=task_queue,
    )

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
    app.state.task_queue = task_queue
    configure_auth_dependencies(settings=settings)

    register_middleware(app)
    register_exception_handlers(app)
    _mount_static(app)
    _register_routes(app)
    _configure_openapi(app, settings)
    return app


def _mount_static(app: FastAPI) -> None:
    WEB_STATIC_DIR.mkdir(parents=True, exist_ok=True)

    assets_dir = WEB_STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def read_spa_root() -> FileResponse:
        if not SPA_INDEX.exists():
            raise HTTPException(status_code=404, detail="SPA build not found")
        return FileResponse(SPA_INDEX)


def _register_routes(app: FastAPI) -> None:
    app.include_router(api_router, prefix=API_PREFIX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def read_spa_fallback(full_path: str, request: Request) -> FileResponse:
        """Serve the SPA entry point for client-side routes."""

        path = request.url.path
        if path == "/" or path.startswith(f"{API_PREFIX}/") or path == API_PREFIX:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        reserved = {app.docs_url, app.redoc_url, app.openapi_url}
        if any(path == candidate for candidate in reserved if candidate):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        filename = full_path.rsplit("/", 1)[-1]
        if "." in filename:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        if not SPA_INDEX.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SPA build not found")

        return FileResponse(SPA_INDEX)


def _configure_openapi(app: FastAPI, settings: Settings) -> None:
    """Configure OpenAPI schema with shared security schemes."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        components = schema.setdefault("components", {}).setdefault(
            "securitySchemes", {}
        )
        components["SessionCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.session_cookie_name,
            "description": "Browser session cookie issued after interactive sign-in.",
        }
        components.setdefault("HTTPBearer", {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Bearer access token returned by ADE or an identity provider.",
        })
        components.setdefault("APIKeyHeader", {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Static API key for service integrations.",
        })

        schema["security"] = [
            {"SessionCookie": []},
            {"HTTPBearer": []},
            {"APIKeyHeader": []},
        ]

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


__all__ = [
    "API_PREFIX",
    "WEB_DIR",
    "WEB_STATIC_DIR",
    "create_app",
]
