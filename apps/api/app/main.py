"""ADE FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .api import register_exception_handlers
from .routers import api_router
from .settings import Settings, get_settings
from .shared.core.lifecycles import create_application_lifespan
from .shared.core.logging import setup_logging
from .shared.core.middleware import register_middleware
from .shared.core.openapi import configure_openapi
from .shared.dependency import configure_auth_dependencies
from .web.spa import mount_spa

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
    app.include_router(api_router, prefix="/api")
    mount_spa(app, api_prefix="/api", static_dir=settings.web_dir / "static")
    configure_openapi(app, settings)
    return app


__all__ = [
    "create_app",
]

app = create_app()
