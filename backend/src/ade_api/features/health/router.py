"""API routes for the health module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ade_api.api.deps import get_health_service_read

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
def read_health(
    service: Annotated[HealthService, Depends(get_health_service_read)],
) -> HealthCheckResponse:
    """Return the current health information for ADE."""
    return service.status()
