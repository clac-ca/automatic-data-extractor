"""Centralized FastAPI exception handlers with structured logging."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from ade_api.common.logging import log_context

_UNHANDLED_LOGGER = logging.getLogger("ade_api.errors")
_HTTP_LOGGER = logging.getLogger("ade_api.http")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Registered as the ``Exception`` handler. Ensures that any unhandled error
    results in:

    * a JSON error response with HTTP 500, and
    * a structured ERROR log including a stack trace.
    """
    _UNHANDLED_LOGGER.exception(
        "unhandled_exception",
        extra=log_context(
            path=str(request.url.path),
            method=request.method,
            exception_type=type(exc).__name__,
            detail=str(exc),
        ),
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for FastAPI HTTPException instances.

    4xx responses (client errors) are returned without logging by default.
    5xx responses are logged at ERROR level with structured metadata.
    """
    if exc.status_code >= 500:
        _HTTP_LOGGER.error(
            "http_exception",
            extra=log_context(
                path=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                detail=exc.detail,
            ),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


__all__ = [
    "http_exception_handler",
    "unhandled_exception_handler",
]
