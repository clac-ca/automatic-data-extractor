"""API routes for the health module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ade.api.settings import get_app_settings
from ade.settings import Settings

from .schemas import HealthCheckResponse
from .service import HealthService

router = APIRouter()


@router.get(
    "",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Service health status",
    response_model_exclude_none=True,
)
async def read_health(
    settings: Annotated[Settings, Depends(get_app_settings)]
) -> HealthCheckResponse:
    """Return the current health information for ADE."""
    service = HealthService(settings=settings)
    return await service.status()
