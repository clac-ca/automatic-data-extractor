"""API error/response compatibility shims."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from pydantic import ConfigDict, Field

from .responses import DefaultResponse, JSONResponse
from .schema import BaseSchema


class ProblemDetail(BaseSchema):
    """Problem+JSON payload compatible with RFC 7807."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
        use_enum_values=True,
        ser_json_timedelta="iso8601",
    )

    type: str = Field(default="about:blank", description="Problem type URI.")
    title: str = Field(description="Short, human-readable summary of the problem.")
    status: int = Field(ge=100, le=599, description="HTTP status code generated.")
    detail: str | None = Field(
        default=None,
        description="Human-readable explanation for this occurrence of the problem.",
    )
    code: str | None = Field(
        default=None,
        description="Application-specific error code.",
    )
    trace_id: str | None = Field(
        default=None,
        description="Correlation identifier for tracing/logging purposes.",
    )
    meta: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata describing the problem.",
    )
    errors: dict[str, list[str]] | None = Field(
        default=None,
        description="Optional field-level validation errors.",
    )


class ProblemException(Exception):
    """Exception signalling an RFC 7807 problem response."""

    def __init__(
        self,
        *,
        status_code: int,
        title: str,
        detail: str | None = None,
        type: str = "about:blank",
        code: str | None = None,
        trace_id: str | None = None,
        meta: dict[str, Any] | None = None,
        errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(title)
        self.problem = ProblemDetail(
            type=type,
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=trace_id,
            meta=meta,
            errors=errors,
        )


def problem_response(
    *,
    status_code: int,
    title: str,
    detail: str | None = None,
    type: str = "about:blank",
    code: str | None = None,
    trace_id: str | None = None,
    meta: dict[str, Any] | None = None,
    errors: dict[str, list[str]] | None = None,
) -> JSONResponse:
    """Return a ``JSONResponse`` encoded as Problem+JSON."""

    problem = ProblemDetail(
        type=type,
        title=title,
        status=status_code,
        detail=detail,
        code=code,
        trace_id=trace_id,
        meta=meta,
        errors=errors,
    )
    return JSONResponse(
        problem,
        status_code=status_code,
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register ADE API exception handlers."""

    @app.exception_handler(ProblemException)
    async def _problem_exception_handler(
        request: Request, exc: ProblemException
    ) -> JSONResponse:
        problem = exc.problem
        if problem.trace_id is None:
            trace_id = getattr(request.state, "trace_id", None)
            if trace_id:
                problem.trace_id = trace_id
        return JSONResponse(
            problem,
            status_code=problem.status,
            media_type="application/problem+json",
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException):
        if (
            exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            and isinstance(exc.detail, list)
        ):
            # Preserve FastAPI's default validation error payload.
            return await fastapi_http_exception_handler(request, exc)

        problem = _coerce_problem_detail(exc.detail, exc.status_code)
        if problem.trace_id is None:
            trace_id = getattr(request.state, "trace_id", None)
            if trace_id:
                problem.trace_id = trace_id
        return JSONResponse(
            problem,
            status_code=exc.status_code,
            media_type="application/problem+json",
            headers=exc.headers,
        )


def _coerce_problem_detail(detail: Any, status_code: int) -> ProblemDetail:
    if isinstance(detail, ProblemDetail):
        return detail
    if isinstance(detail, dict):
        data = detail.copy()
        raw_meta = data.pop("meta", None)
        detail_text = data.pop("detail", None)
        if detail_text is None and isinstance(data.get("message"), str):
            detail_text = data.pop("message")
        code = data.pop("code", None)
        if code is None and isinstance(data.get("error"), str):
            code = data.pop("error")
        trace_id = data.pop("trace_id", None)
        errors_field = data.pop("errors", None)
        type_value = data.pop("type", "about:blank")
        title_value = data.pop("title", _status_title(status_code))
        status_value = data.pop("status", status_code)
        remainder = data if data else None
        meta = raw_meta
        if remainder:
            if isinstance(meta, dict):
                merged = remainder.copy()
                merged.update(meta)
                meta = merged
            elif meta is None:
                meta = remainder
        return ProblemDetail(
            type=type_value,
            title=title_value,
            status=status_value,
            detail=detail_text,
            code=code,
            trace_id=trace_id,
            meta=meta,
            errors=errors_field,
        )
    message = detail if isinstance(detail, str) else None
    return ProblemDetail(
        type="about:blank",
        title=_status_title(status_code),
        status=status_code,
        detail=message,
    )


def _status_title(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:  # pragma: no cover
        return "HTTP Error"


__all__ = [
    "DefaultResponse",
    "JSONResponse",
    "ProblemDetail",
    "ProblemException",
    "problem_response",
    "register_exception_handlers",
]
