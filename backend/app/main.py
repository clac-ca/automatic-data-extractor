"""FastAPI application factory for the ADE backend."""

from __future__ import annotations

from fastapi import FastAPI

from .api import register_routers
from .core.logging import setup_logging
from .core.message_hub import MessageHub
from .core.settings import AppSettings, get_settings
from .extensions.middleware import register_middleware


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Instantiate and configure the FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings)

    docs_url, redoc_url = settings.docs_urls
    openapi_url = settings.openapi_url if settings.enable_docs else None

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        debug=settings.debug,
    )

    app.state.settings = settings
    app.state.message_hub = MessageHub()

    register_middleware(app)
    register_routers(app)

    return app


app = create_app()
