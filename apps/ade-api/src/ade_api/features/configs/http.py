"""Shared HTTP helpers for the configuration feature."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import HTTPException, Path

WorkspaceIdPath = Annotated[
    UUID,
    Path(
        ...,
        description="Workspace identifier",
    ),
]
ConfigurationIdPath = Annotated[
    UUID,
    Path(
        ...,
        description="Configuration identifier",
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
    """Raise a Problem Details-style HTTPException."""

    payload = {
        "type": "about:blank",
        "title": title or code.replace("_", " ").title(),
        "status": status_code,
        "detail": detail,
        "code": code,
    }
    if meta:
        payload["meta"] = meta
    raise HTTPException(status_code, detail=payload)


__all__ = ["ConfigurationIdPath", "WorkspaceIdPath", "raise_problem"]
