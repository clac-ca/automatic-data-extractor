from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

logger = logging.getLogger(__name__)


def error_envelope(code: str, message: str, *, trace_id: str | None = None, data: Any | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if trace_id:
        payload["trace_id"] = trace_id
    if data is not None:
        payload["data"] = data
    return payload


class ApplicationError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def _handle_application_error(_: Request, exc: ApplicationError) -> JSONResponse:
        trace_id = str(uuid.uuid4())
        logger.warning("application error (%s): %s", exc.code, exc, extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(code=exc.code, message=str(exc), trace_id=trace_id),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        trace_id = str(uuid.uuid4())
        logger.info("validation error: %s", exc.errors(), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_envelope(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                trace_id=trace_id,
                data={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        trace_id = str(uuid.uuid4())
        logger.exception("unexpected error", exc_info=exc, extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_envelope(code="SERVER_ERROR", message="Internal server error", trace_id=trace_id),
        )
