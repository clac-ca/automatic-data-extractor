"""FastAPI application factory for the ADE backend."""

from __future__ import annotations

from fastapi import FastAPI

from .api import register_routers
from .core.logging import setup_logging
from .core.message_hub import MessageHub
from .core.settings import AppSettings, get_settings
from .db.session import get_sessionmaker
from .modules.events.recorder import EventRecorder
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
    message_hub = MessageHub()
    app.state.message_hub = message_hub

    session_factory = get_sessionmaker(settings)
    event_recorder = EventRecorder(session_factory)
    message_hub.subscribe_all(event_recorder)
    app.state.event_recorder = event_recorder

    def _shutdown_event_recorder() -> None:
        message_hub.unsubscribe("*", event_recorder)

    app.add_event_handler("shutdown", _shutdown_event_recorder)

    register_middleware(app)
    register_routers(app)

    return app


app = create_app()
