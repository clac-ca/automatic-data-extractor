"""Problem Details helpers for consistent API error responses."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import status
from pydantic import Field

from .schema import BaseSchema


@dataclass(frozen=True)
class ErrorDefinition:
    """Canonical Problem Details error metadata."""

    type: str
    title: str
    status: int


ERROR_DEFINITIONS: dict[str, ErrorDefinition] = {
    "bad_request": ErrorDefinition(
        type="bad_request",
        title="Bad request",
        status=status.HTTP_400_BAD_REQUEST,
    ),
    "unauthorized": ErrorDefinition(
        type="unauthorized",
        title="Unauthorized",
        status=status.HTTP_401_UNAUTHORIZED,
    ),
    "forbidden": ErrorDefinition(
        type="forbidden",
        title="Forbidden",
        status=status.HTTP_403_FORBIDDEN,
    ),
    "not_found": ErrorDefinition(
        type="not_found",
        title="Not found",
        status=status.HTTP_404_NOT_FOUND,
    ),
    "conflict": ErrorDefinition(
        type="conflict",
        title="Conflict",
        status=status.HTTP_409_CONFLICT,
    ),
    "resync_required": ErrorDefinition(
        type="resync_required",
        title="Resync required",
        status=status.HTTP_410_GONE,
    ),
    "precondition_failed": ErrorDefinition(
        type="precondition_failed",
        title="Precondition failed",
        status=status.HTTP_412_PRECONDITION_FAILED,
    ),
    "validation_error": ErrorDefinition(
        type="validation_error",
        title="Validation error",
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    "precondition_required": ErrorDefinition(
        type="precondition_required",
        title="Precondition required",
        status=status.HTTP_428_PRECONDITION_REQUIRED,
    ),
    "rate_limited": ErrorDefinition(
        type="rate_limited",
        title="Too many requests",
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    ),
    "service_unavailable": ErrorDefinition(
        type="service_unavailable",
        title="Service unavailable",
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    ),
    "internal_error": ErrorDefinition(
        type="internal_error",
        title="Internal server error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    ),
}

STATUS_TO_ERROR_TYPE: dict[int, ErrorDefinition] = {
    definition.status: definition for definition in ERROR_DEFINITIONS.values()
}


class ProblemDetailsErrorItem(BaseSchema):
    """Structured error detail used for validation-style responses."""

    path: str | None = None
    message: str
    code: str | None = None


class ProblemDetails(BaseSchema):
    """Problem Details-style response payload."""

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str
    request_id: str | None = Field(default=None, alias="requestId")
    errors: list[ProblemDetailsErrorItem] | None = None


class ApiError(RuntimeError):
    """Custom exception carrying Problem Details metadata."""

    def __init__(
        self,
        *,
        error_type: str,
        status_code: int,
        detail: str | None = None,
        title: str | None = None,
        errors: list[ProblemDetailsErrorItem] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or title or error_type)
        self.error_type = error_type
        self.status_code = status_code
        self.detail = detail
        self.title = title
        self.errors = errors
        self.headers = headers


def resolve_error_definition(status_code: int) -> ErrorDefinition:
    """Return the canonical error definition for ``status_code``."""

    return STATUS_TO_ERROR_TYPE.get(
        status_code,
        ErrorDefinition(type="error", title="Error", status=status_code),
    )


def format_error_path(loc: Iterable[Any] | None) -> str | None:
    """Convert a Pydantic-style loc tuple/list into a dotted path."""

    if not loc:
        return None
    parts: list[str] = []
    for entry in loc:
        if entry in {"body", "query", "path", "header", "cookie"}:
            continue
        if isinstance(entry, int):
            if not parts:
                parts.append(f"[{entry}]")
            else:
                parts[-1] = f"{parts[-1]}[{entry}]"
            continue
        parts.append(str(entry))
    if not parts:
        return None
    joined = ".".join(parts)
    return joined.replace(".[", "[")


def error_items_from_pydantic(errors: Iterable[dict[str, Any]]) -> list[ProblemDetailsErrorItem]:
    """Convert Pydantic error dicts into Problem Details error items."""

    items: list[ProblemDetailsErrorItem] = []
    for entry in errors:
        loc = entry.get("loc") or entry.get("path")
        message = entry.get("msg") or entry.get("message") or "Invalid value"
        code = entry.get("type") or entry.get("code")
        path_value: str | None
        if isinstance(loc, (list, tuple)):
            path_value = format_error_path(loc)
        elif isinstance(loc, str):
            path_value = loc
        else:
            path_value = None
        items.append(
            ProblemDetailsErrorItem(
                path=path_value,
                message=str(message),
                code=str(code) if code else None,
            )
        )
    return items


def coerce_detail_and_errors(detail: Any) -> tuple[str | None, list[ProblemDetailsErrorItem] | None]:
    """Normalize mixed ``detail`` payloads into a detail string + error items."""

    if detail is None:
        return None, None

    if isinstance(detail, ProblemDetails):
        return detail.detail, detail.errors

    if isinstance(detail, list):
        return None, error_items_from_pydantic(detail)

    if isinstance(detail, dict):
        detail_text: str | None = None
        errors: list[ProblemDetailsErrorItem] | None = None

        if "errors" in detail and isinstance(detail["errors"], list):
            errors = error_items_from_pydantic(detail["errors"])

        if "issues" in detail and isinstance(detail["issues"], list):
            issues = error_items_from_pydantic(detail["issues"])
            if issues:
                errors = issues
                if detail_text is None:
                    detail_text = "Validation error"

        if "detail" in detail and isinstance(detail["detail"], str):
            detail_text = detail["detail"]
        elif "message" in detail and isinstance(detail["message"], str):
            detail_text = detail["message"]

        if "error" in detail:
            error_payload = detail["error"]
            if isinstance(error_payload, dict):
                code = error_payload.get("code") or error_payload.get("error")
                message = error_payload.get("message") or error_payload.get("detail")
                detail_text = detail_text or message or (str(code) if code else None)
                if errors is None and (code or message):
                    errors = [
                        ProblemDetailsErrorItem(
                            message=str(message or detail_text or "Request failed"),
                            code=str(code) if code else None,
                        )
                    ]
            else:
                code = str(error_payload)
                detail_text = detail_text or detail.get("message") or code
                if errors is None:
                    errors = [
                        ProblemDetailsErrorItem(
                            message=str(detail_text or "Request failed"),
                            code=code,
                        )
                    ]
        elif "code" in detail and isinstance(detail.get("code"), str):
            code = detail["code"]
            detail_text = detail_text or detail.get("message") or code
            if errors is None:
                errors = [
                    ProblemDetailsErrorItem(
                        message=str(detail_text or "Request failed"),
                        code=code,
                    )
                ]

        if "latest_cursor" in detail:
            cursor = detail.get("latest_cursor")
            if cursor:
                suffix = f" (latest_cursor={cursor})"
                detail_text = (detail_text or "Resync required") + suffix

        if "limit" in detail:
            detail_text = (
                f"{detail_text} (limit={detail['limit']})" if detail_text else f"Limit {detail['limit']}"
            )

        return detail_text, errors

    if isinstance(detail, str):
        return detail, None

    return str(detail), None


def build_problem_details(
    *,
    status_code: int,
    instance: str,
    request_id: str | None,
    detail: str | None = None,
    errors: list[ProblemDetailsErrorItem] | None = None,
    error_type: str | None = None,
    title: str | None = None,
) -> ProblemDetails:
    """Construct a Problem Details payload."""

    definition = resolve_error_definition(status_code)
    resolved_type = error_type or definition.type
    resolved_title = title or definition.title
    return ProblemDetails(
        type=resolved_type,
        title=resolved_title,
        status=status_code,
        detail=detail,
        instance=instance,
        request_id=request_id,
        errors=errors,
    )


__all__ = [
    "ApiError",
    "ProblemDetails",
    "ProblemDetailsErrorItem",
    "build_problem_details",
    "coerce_detail_and_errors",
    "error_items_from_pydantic",
    "resolve_error_definition",
]
