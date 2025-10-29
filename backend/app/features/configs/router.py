"""Placeholder router for configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(
    prefix="/workspaces/{workspace_id}/configs",
    tags=["configs"],
)


@router.get(
    "",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="List configuration packages (placeholder)",
)
async def list_configs_placeholder() -> dict[str, str]:
    """Placeholder endpoint for future configuration package support."""

    return {"detail": "Configuration APIs are not implemented yet."}


__all__ = ["router"]
