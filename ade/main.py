"""ADE FastAPI application entry point."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.v1.router import router as api_router
from .settings import Settings, get_settings
from .core.logging import setup_logging
from .core.middleware import register_middleware
from .api.errors import register_exception_handlers
from .lifecycles import create_application_lifespan
from .features.auth.dependencies import configure_auth_dependencies
from .services.task_queue import TaskQueue

WEB_DIR = Path(__file__).resolve().parent / "web"
WEB_STATIC_DIR = WEB_DIR / "static"
SPA_INDEX = WEB_STATIC_DIR / "index.html"
API_PREFIX = "/api"
DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
FRONTEND_BUILD_DIRNAME = Path("dist")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Return a configured FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings)

    docs_url = settings.docs_url if settings.api_docs_enabled else None
    redoc_url = settings.redoc_url if settings.api_docs_enabled else None
    openapi_url = settings.openapi_url if settings.api_docs_enabled else None

    task_queue = TaskQueue()
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
        print("Frontend: rebuilt and synced to ade/web/static")
    else:
        print("Frontend: serving existing assets from ade/web/static")

    print("ADE application server")
    print("---------------------")
    print(f"Listening on http://{bind_host}:{bind_port}")
    print(f"Reload: {'enabled' if reload else 'disabled'}\n")

    import uvicorn

    target = "ade.main:create_app" if reload else create_app
    uvicorn.run(
        target,
        host=bind_host,
        port=bind_port,
        reload=reload,
        factory=True,
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

    browser_dir = build_dir / "browser"
    if browser_dir.exists() and browser_dir.is_dir():
        primary_sources = list(browser_dir.iterdir())
        extra_sources = [path for path in build_dir.iterdir() if path.name != "browser"]
    else:
        primary_sources = list(build_dir.iterdir())
        extra_sources: list[Path] = []

    target = Path(static_dir).expanduser().resolve() if static_dir else WEB_STATIC_DIR
    target.mkdir(parents=True, exist_ok=True)

    for entry in target.iterdir():
        if entry.name == "README.md":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()

    def _copy_path(source: Path, destination: Path) -> None:
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)

    for source in primary_sources:
        _copy_path(source, target / source.name)

    for source in extra_sources:
        destination = target / source.name
        _copy_path(source, destination)


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
    "DEFAULT_FRONTEND_DIR",
    "FRONTEND_BUILD_DIRNAME",
    "WEB_DIR",
    "WEB_STATIC_DIR",
    "build_frontend_assets",
    "create_app",
    "start",
    "sync_frontend_assets",
]
