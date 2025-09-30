"""Utilities for composing workspace-scoped routers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def workspace_scoped_router(
    *,
    subpath: str = "",
    tags: list[str] | None = None,
    **router_kwargs: Any,
) -> APIRouter:
    """Return an ``APIRouter`` prefixed with the workspace path segment."""

    normalized = subpath.strip()
    if normalized and not normalized.startswith("/"):
        normalized = f"/{normalized}"

    prefix = f"/workspaces/{{workspace_id}}{normalized}"
    return APIRouter(prefix=prefix, tags=tags, **router_kwargs)


__all__ = ["workspace_scoped_router"]
