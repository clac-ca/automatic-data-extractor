"""ADE FastAPI application entry point."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .api import register_exception_handlers
from .shared.dependency import configure_auth_dependencies
from .settings import Settings, get_settings
from .shared.core.lifecycles import create_application_lifespan
from .shared.core.logging import setup_logging
from .shared.core.middleware import register_middleware

API_PREFIX = "/api"
API_VERSION_PREFIX = "/v1"
SPA_CACHE_HEADERS = {"Cache-Control": "no-cache"}
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Return a configured FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings)

    docs_url = settings.docs_url if settings.api_docs_enabled else None
    redoc_url = settings.redoc_url if settings.api_docs_enabled else None
    openapi_url = settings.openapi_url if settings.api_docs_enabled else None

    lifespan = create_application_lifespan(
        settings=settings,
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
    app.state.safe_mode = bool(settings.safe_mode)
    if settings.safe_mode:
        logger.warning(
            "ADE safe mode enabled; user-submitted configuration code will not execute.",
            extra={"safe_mode": True},
        )
    configure_auth_dependencies(settings=settings)

    register_middleware(app)
    register_exception_handlers(app)
    web_static_dir = settings.web_dir / "static"
    spa_index = web_static_dir / "index.html"
    _mount_static(app, web_static_dir=web_static_dir, spa_index=spa_index)
    _register_routes(app, spa_index=spa_index)
    _configure_openapi(app, settings)
    return app


def _mount_static(app: FastAPI, *, web_static_dir: Path, spa_index: Path) -> None:
    if web_static_dir.exists():
        assets_dir = web_static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        favicon = web_static_dir / "favicon.ico"
        if favicon.exists():
            @app.get("/favicon.ico", include_in_schema=False)
            async def favicon_ico() -> FileResponse:
                return FileResponse(favicon)

    @app.get("/", include_in_schema=False)
    async def read_spa_root() -> Response:
        if not spa_index.exists():
            raise HTTPException(status_code=404, detail="SPA build not found")
        return FileResponse(spa_index, headers=SPA_CACHE_HEADERS)


def _register_routes(app: FastAPI, *, spa_index: Path) -> None:
    api_router = _build_api_router()
    app.include_router(api_router, prefix=API_PREFIX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def read_spa_fallback(full_path: str, request: Request) -> Response:
        """Serve the SPA entry point for client-side routes."""

        path = request.url.path
        if path == "/" or path.startswith(f"{API_PREFIX}/") or path == API_PREFIX:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        reserved = {app.docs_url, app.redoc_url, app.openapi_url}
        if any(path == candidate for candidate in reserved if candidate):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        if not _wants_html(request):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        filename = full_path.rsplit("/", 1)[-1]
        if "." in filename:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")

        if not spa_index.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SPA build not found")

        return FileResponse(spa_index, headers=SPA_CACHE_HEADERS)


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
        schema["servers"] = [{"url": settings.server_public_url}]

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


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower()


def _build_api_router() -> APIRouter:
    """Compose the versioned API router from feature modules."""

    from .features.auth.router import router as auth_router
    from .features.auth.router import setup_router
    from .features.documents.router import router as documents_router
    from .features.health.router import router as health_router
    from .features.roles.router import router as roles_router
    from .features.users.router import router as users_router
    from .features.workspaces.router import router as workspaces_router

    router = APIRouter(prefix=API_VERSION_PREFIX)
    router.include_router(health_router, prefix="/health", tags=["health"])
    router.include_router(setup_router)
    router.include_router(auth_router)
    router.include_router(users_router)
    router.include_router(roles_router)
    router.include_router(workspaces_router)
    router.include_router(documents_router)
    return router


__all__ = [
    "API_PREFIX",
    "create_app",
]

app = create_app()
