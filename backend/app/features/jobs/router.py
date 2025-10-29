"""Placeholder router for job orchestration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(
    prefix="/workspaces/{workspace_id}/jobs",
    tags=["jobs"],
)


@router.get(
    "",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="List jobs (placeholder)",
)
async def list_jobs_placeholder() -> dict[str, str]:
    """Placeholder endpoint for future job management support."""

    return {"detail": "Job APIs are not implemented yet."}


__all__ = ["router"]
