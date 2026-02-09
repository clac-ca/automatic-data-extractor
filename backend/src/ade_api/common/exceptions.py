"""Centralized FastAPI exception handlers with structured logging."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from ade_api.common.logging import log_context
from ade_api.common.problem_details import (
    ApiError,
    ProblemDetailsErrorItem,
    build_problem_details,
    coerce_detail_and_errors,
    error_items_from_pydantic,
    resolve_error_definition,
)
from ade_api.common.responses import JSONResponse

_UNHANDLED_LOGGER = logging.getLogger("ade_api.errors")
_HTTP_LOGGER = logging.getLogger("ade_api.http")
_PROBLEM_MEDIA_TYPE = "application/problem+json"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _problem_response(
    *,
    request: Request,
    status_code: int,
    detail: str | dict[str, object] | None,
    errors: list[ProblemDetailsErrorItem] | None,
    error_type: str | None = None,
    title: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    problem = build_problem_details(
        status_code=status_code,
        instance=str(request.url.path),
        request_id=_request_id(request),
        detail=detail,
        errors=errors,
        error_type=error_type,
        title=title,
    )
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(by_alias=True, exclude_none=True),
        media_type=_PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
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

    return _problem_response(
        request=request,
        status_code=500,
        detail="Internal server error",
        errors=None,
        error_type=resolve_error_definition(500).type,
    )


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
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

    error_type: str | None = None
    title: str | None = None
    if isinstance(exc.detail, dict):
        error_type = exc.detail.get("type") if isinstance(exc.detail.get("type"), str) else None
        title = exc.detail.get("title") if isinstance(exc.detail.get("title"), str) else None

    detail_text, errors = coerce_detail_and_errors(exc.detail)
    if errors and detail_text is None and exc.status_code == 422:
        detail_text = "Invalid request"
    # Keep opaque responses for unexpected internal errors, while preserving
    # explicit upstream/service error contracts for non-500 statuses (e.g. 502).
    if exc.status_code == 500:
        detail_text = "Internal server error"
        errors = None

    return _problem_response(
        request=request,
        status_code=exc.status_code,
        detail=detail_text,
        errors=errors,
        error_type=error_type,
        title=title,
        headers=getattr(exc, "headers", None),
    )


def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = error_items_from_pydantic(exc.errors())
    return _problem_response(
        request=request,
        status_code=422,
        detail="Invalid request",
        errors=errors,
        error_type=resolve_error_definition(422).type,
    )


def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    detail_text, errors = coerce_detail_and_errors(exc.detail)
    return _problem_response(
        request=request,
        status_code=exc.status_code,
        detail=detail_text,
        errors=errors or exc.errors,
        error_type=exc.error_type,
        title=exc.title,
        headers=exc.headers,
    )


__all__ = [
    "api_error_handler",
    "http_exception_handler",
    "request_validation_exception_handler",
    "unhandled_exception_handler",
]
