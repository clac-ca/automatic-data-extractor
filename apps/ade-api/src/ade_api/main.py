"""ADE FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.v1.router import create_api_router
from .app.lifecycles import create_application_lifespan
from .common.exceptions import (
    api_error_handler,
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from .common.logging import log_context, setup_logging
from .common.middleware import register_middleware
from .common.openapi import configure_openapi
from .common.problem_details import ApiError
from .common.time import utc_now
from .core.http.errors import register_auth_exception_handlers
from .features.health.ops import router as ops_router
from .settings import Settings, get_settings
from .web.spa import mount_spa

logger = logging.getLogger(__name__)

API_PREFIX = "/api"


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
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    register_auth_exception_handlers(app)

    # Application state and startup metadata.
    app.state.settings = settings
    app.state.safe_mode = bool(settings.safe_mode)
    app.state.started_at = utc_now()

    logger.info(
        "ade_api.startup",
        extra=log_context(
            logging_level=settings.logging_level,
            safe_mode=bool(settings.safe_mode),
            auth_disabled=bool(settings.auth_disabled),
            version=settings.app_version,
        ),
    )
    if settings.jwt_secret_generated:
        logger.error(
            (
                "ADE_JWT_SECRET was not configured; generated a random secret. "
                "Session cookies and bearer tokens will be invalidated on restart and "
                "cannot be shared across replicas. Set ADE_JWT_SECRET to a long random "
                "string (>=32 chars), e.g. python - <<'PY'\\nimport secrets; "
                "print(secrets.token_urlsafe(64))\\nPY"
            ),
            extra=log_context(jwt_secret_generated=True),
        )

    if settings.safe_mode:
        logger.warning(
            "safe_mode.enabled",
            extra=log_context(safe_mode=True),
        )

    if settings.auth_disabled:
        logger.warning(
            "auth.disabled",
            extra=log_context(auth_disabled=True),
        )

    # Middleware, routers, and OpenAPI configuration.
    register_middleware(app, settings=settings)
    app.include_router(ops_router, include_in_schema=False)
    app.include_router(create_api_router(settings), prefix=API_PREFIX)
    configure_openapi(app, settings)

    mount_spa(app, settings.frontend_dist_dir)

    return app


__all__ = [
    "API_PREFIX",
    "create_app",
]

# ASGI entrypoint used by uvicorn / gunicorn.
app = create_app()
