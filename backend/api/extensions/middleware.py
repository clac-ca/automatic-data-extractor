"""Custom FastAPI middleware components."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from ..core.logging import bind_request_context, clear_request_context

_REQUEST_LOGGER = logging.getLogger("ade.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach correlation IDs and emit structured request logs."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        correlation_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.correlation_id = correlation_id
        bind_request_context(correlation_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - defensive logging path
            duration_ms = (time.perf_counter() - start) * 1000
            _REQUEST_LOGGER.exception(
                "request.error",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": correlation_id,
                },
            )
            raise
        else:
            duration_ms = (time.perf_counter() - start) * 1000
            _REQUEST_LOGGER.info(
                "request.complete",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": correlation_id,
                },
            )
        finally:
            clear_request_context()

        response.headers["X-Request-ID"] = correlation_id
        return response


def register_middleware(app: FastAPI) -> None:
    """Register ADE default middleware on the FastAPI application."""

    app.add_middleware(RequestContextMiddleware)


__all__ = ["RequestContextMiddleware", "register_middleware"]
