"""API route exposing runtime metadata."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from ade_api.api.deps import SettingsDep
from ade_api.common.time import utc_now

from .schemas import InfoResponse

router = APIRouter(tags=["info"])


@router.get(
    "/info",
    response_model=InfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Runtime metadata",
)
async def read_info(
    request: Request,
    settings: SettingsDep,
) -> InfoResponse:
    started_at = getattr(request.app.state, "started_at", None) or utc_now()
    return InfoResponse(
        version=settings.app_version,
        commit_sha=settings.app_commit_sha or "unknown",
        environment=settings.app_environment or "unknown",
        started_at=started_at,
    )


__all__ = ["router"]
