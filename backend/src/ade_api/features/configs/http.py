"""Shared HTTP helpers for the configuration feature."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Path

from ade_api.common.problem_details import (
    ApiError,
    ProblemDetailsErrorItem,
    resolve_error_definition,
)

WorkspaceIdPath = Annotated[
    UUID,
    Path(
        ...,
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
ConfigurationIdPath = Annotated[
    UUID,
    Path(
        ...,
        description="Configuration identifier",
        alias="configurationId",
    ),
]


def raise_problem(
    code: str,
    status_code: int,
    *,
    detail: str | None = None,
    title: str | None = None,
    meta: dict | None = None,
) -> None:
    """Raise a Problem Details-style API error."""

    detail_text = detail
    if meta:
        meta_bits = ", ".join(
            f"{key}={value}" for key, value in meta.items() if value is not None
        )
        if meta_bits:
            detail_text = f"{detail_text} ({meta_bits})" if detail_text else meta_bits

    definition = resolve_error_definition(status_code)
    if code in {"precondition_required", "precondition_failed"}:
        error_type = code
    else:
        error_type = definition.type
    errors = None
    if code not in {definition.type, "precondition_required", "precondition_failed"}:
        errors = [
            ProblemDetailsErrorItem(
                message=detail_text or title or code.replace("_", " ").title(),
                code=code,
            )
        ]
    raise ApiError(
        error_type=error_type,
        status_code=status_code,
        detail=detail_text,
        title=title,
        errors=errors,
    )


__all__ = ["ConfigurationIdPath", "WorkspaceIdPath", "raise_problem"]
