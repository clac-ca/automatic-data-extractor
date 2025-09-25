"""FastAPI application factory for the ADE backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app import Settings, get_settings

from .api import register_routers
from .core.logging import setup_logging
from .core.message_hub import MessageHub
from .core.task_queue import TaskQueue
from .extensions.middleware import register_middleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Instantiate and configure the FastAPI application."""

    settings = settings or get_settings()
    setup_logging(settings)

    docs_url, redoc_url = settings.docs_urls
    openapi_url = settings.openapi_url if settings.enable_docs else None

    message_hub = MessageHub()
    task_queue = TaskQueue()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.message_hub = message_hub
        app.state.task_queue = task_queue
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
    register_routers(app)
    return app


app = create_app()
