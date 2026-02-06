"""Optimistic concurrency helpers (ETag + If-Match)."""

from __future__ import annotations

from fastapi import status

from ade_api.common.etag import canonicalize_etag, format_weak_etag
from ade_api.common.problem_details import ApiError, ProblemDetailsErrorItem


def require_if_match(
    if_match: str | None,
    *,
    expected_token: str,
) -> None:
    """Enforce presence and correctness of the If-Match header."""

    if not if_match:
        raise ApiError(
            error_type="precondition_required",
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required.",
            errors=[
                ProblemDetailsErrorItem(
                    path="If-Match",
                    message="Missing If-Match header.",
                    code="precondition_required",
                )
            ],
        )

    if canonicalize_etag(if_match) != expected_token:
        current = format_weak_etag(expected_token)
        detail = "ETag mismatch."
        if current:
            detail = f"{detail} Current ETag: {current}"
        raise ApiError(
            error_type="precondition_failed",
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=detail,
            errors=[
                ProblemDetailsErrorItem(
                    path="If-Match",
                    message="ETag does not match the current resource.",
                    code="precondition_failed",
                )
            ],
        )


__all__ = ["require_if_match"]
