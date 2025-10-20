from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from .api.v1 import api_router as api_v1_router
from .api.v1.health import router as health_router
from .core.config import settings
from .core.errors import register_exception_handlers
from .core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
    )

    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

    # Public health endpoints
    app.include_router(health_router, prefix="/api")
    # Versioned application routers
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    # Serve pre-built frontend if available
    if settings.static_dir.exists():
        app.mount(
            settings.static_mount_path,
            StaticFiles(directory=settings.static_dir, html=True),
            name="static",
        )

    register_exception_handlers(app)
    return app


app = create_app()
