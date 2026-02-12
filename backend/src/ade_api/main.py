"""ADE FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from .api.v1.router import create_api_router
from .app.lifecycles import create_application_lifespan
from .common.api_docs import register_api_docs_routes
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
from .features.scim.errors import ScimApiError
from .features.scim.handlers import scim_api_error_handler
from .features.scim.router import router as scim_router
from .settings import Settings, get_settings

API_PREFIX = "/api"
type HttpExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]
logger = logging.getLogger(__name__)


def _as_http_exception_handler(handler: Callable[..., Response]) -> HttpExceptionHandler:
    return cast(HttpExceptionHandler, handler)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the ADE FastAPI application."""
    # Settings + logging first so everything else uses the configured root logger.
    settings = settings or get_settings()
    setup_logging(settings)

    lifespan = create_application_lifespan(settings=settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
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
    app.add_exception_handler(ScimApiError, _as_http_exception_handler(scim_api_error_handler))
    app.add_exception_handler(Exception, _as_http_exception_handler(unhandled_exception_handler))
    register_auth_exception_handlers(app)

    # Middleware, routers, and OpenAPI configuration.
    register_middleware(app, settings=settings)
    app.include_router(ops_router, include_in_schema=False)
    app.include_router(create_api_router(), prefix=API_PREFIX)
    app.include_router(scim_router)
    configure_openapi(app, settings)
    if settings.api_docs_enabled:
        register_api_docs_routes(app, settings=settings)
        logger.info(
            "api.docs.enabled",
            extra={
                "access_mode": settings.api_docs_access_mode,
                "redoc_url": settings.redoc_url,
                "swagger_url": settings.docs_url,
                "openapi_url": settings.openapi_url,
            },
        )

    return app


__all__ = [
    "API_PREFIX",
    "create_app",
]
