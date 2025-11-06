"""API error/response compatibility shims."""

from __future__ import annotations

from fastapi import FastAPI, Request
from pydantic import Field

from .responses import DefaultResponse, JSONResponse
from .schema import BaseSchema


class ProblemDetail(BaseSchema):
    """Problem+JSON payload compatible with RFC 7807."""

    type: str = Field(default="about:blank", description="Problem type URI.")
    title: str = Field(description="Short, human-readable summary of the problem.")
    status: int = Field(ge=100, le=599, description="HTTP status code generated.")
    detail: str | None = Field(
        default=None,
        description="Human-readable explanation for this occurrence of the problem.",
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
        errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(title)
        self.problem = ProblemDetail(
            type=type,
            title=title,
            status=status_code,
            detail=detail,
            errors=errors,
        )


def problem_response(
    *,
    status_code: int,
    title: str,
    detail: str | None = None,
    type: str = "about:blank",
    errors: dict[str, list[str]] | None = None,
) -> JSONResponse:
    """Return a ``JSONResponse`` encoded as Problem+JSON."""

    problem = ProblemDetail(
        type=type,
        title=title,
        status=status_code,
        detail=detail,
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
        return JSONResponse(
            exc.problem,
            status_code=exc.problem.status,
            media_type="application/problem+json",
        )


__all__ = [
    "DefaultResponse",
    "JSONResponse",
    "ProblemDetail",
    "ProblemException",
    "problem_response",
    "register_exception_handlers",
]
