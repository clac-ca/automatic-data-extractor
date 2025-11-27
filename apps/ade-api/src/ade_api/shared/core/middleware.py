"""Custom FastAPI middleware components."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from ade_api.settings import get_settings

from .logging import bind_request_context, clear_request_context, log_context

_REQUEST_LOGGER = logging.getLogger("ade_api.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach correlation IDs and emit structured request logs."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:

        correlation_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.correlation_id = correlation_id
        bind_request_context(correlation_id)

        start = time.perf_counter()
        response: Response | None = None
        error: bool = False

        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - defensive logging path
            error = True
            # Stack trace will be logged by the global exception handler.
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0

            extra = log_context(
                path=request.url.path,
                method=request.method,
                duration_ms=round(duration_ms, 2),
                status_code=response.status_code if response is not None else None,
            )

            if not error and response is not None:
                _REQUEST_LOGGER.info("request.complete", extra=extra)
            else:
                _REQUEST_LOGGER.error("request.error", extra=extra)

            clear_request_context()

        if response is None:  # pragma: no cover - defensive guard
            raise RuntimeError("Request handler returned no response")

        response.headers["X-Request-ID"] = correlation_id
        return response


def register_middleware(app: FastAPI) -> None:
    """Register ADE default middleware on the FastAPI application."""

    settings = get_settings()

    origins = list(settings.server_cors_origins)
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestContextMiddleware)


__all__ = ["RequestContextMiddleware", "register_middleware"]
