"""ADE FastAPI application entry point."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from .api.v1.router import create_api_router
from .app.lifecycles import create_application_lifespan
from .common.exceptions import (
    api_error_handler,
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from .common.logging import setup_logging
from .common.middleware import register_middleware
from .common.openapi import configure_openapi
from .common.problem_details import ApiError
from .core.http.errors import register_auth_exception_handlers
from .features.health.ops import router as ops_router
from .settings import Settings, get_settings

API_PREFIX = "/api"
type HttpExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


def _as_http_exception_handler(handler: Callable[..., Response]) -> HttpExceptionHandler:
    return cast(HttpExceptionHandler, handler)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the ADE FastAPI application."""
    # Settings + logging first so everything else uses the configured root logger.
    settings = settings or get_settings()
    setup_logging(settings)

    docs_url = settings.docs_url if settings.api_docs_enabled else None
    redoc_url = settings.redoc_url if settings.api_docs_enabled else None
    openapi_url = settings.openapi_url if settings.api_docs_enabled else None

    lifespan = create_application_lifespan(settings=settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        debug=False,
        lifespan=lifespan,
    )

    # Global exception handlers.
    app.add_exception_handler(
        RequestValidationError, _as_http_exception_handler(request_validation_exception_handler)
    )
    app.add_exception_handler(HTTPException, _as_http_exception_handler(http_exception_handler))
    app.add_exception_handler(
        StarletteHTTPException, _as_http_exception_handler(http_exception_handler)
    )
    app.add_exception_handler(ApiError, _as_http_exception_handler(api_error_handler))
    app.add_exception_handler(Exception, _as_http_exception_handler(unhandled_exception_handler))
    register_auth_exception_handlers(app)

    # Middleware, routers, and OpenAPI configuration.
    register_middleware(app, settings=settings)
    app.include_router(ops_router, include_in_schema=False)
    app.include_router(create_api_router(), prefix=API_PREFIX)
    configure_openapi(app, settings)

    return app


__all__ = [
    "API_PREFIX",
    "create_app",
]
