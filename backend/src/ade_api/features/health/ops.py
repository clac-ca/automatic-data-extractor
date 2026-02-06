"""Operational liveness/readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import text

from ade_api.api.deps import ReadSessionDep, SettingsDep
from ade_api.common.problem_details import ApiError
from ade_api.common.time import utc_now

from .schemas import HealthCheckResponse, HealthComponentStatus
from .service import HealthService

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Service liveness probe",
    response_model_exclude_none=True,
)
def read_liveness(settings: SettingsDep) -> HealthCheckResponse:
    """Return liveness status without touching the database."""

    service = HealthService(settings=settings, safe_mode_service=None)
    return service.status()


@router.get(
    "/ready",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Service readiness probe",
    response_model_exclude_none=True,
)
def read_readiness(settings: SettingsDep, db: ReadSessionDep) -> HealthCheckResponse:
    """Return readiness status after checking critical dependencies."""

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - exercised in integration tests
        raise ApiError(
            error_type="service_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return HealthCheckResponse(
        status="ok",
        timestamp=utc_now(),
        components=[
            HealthComponentStatus(
                name="api",
                status="available",
                detail=f"v{settings.app_version}",
            ),
            HealthComponentStatus(
                name="database",
                status="available",
                detail="connected",
            ),
        ],
    )


__all__ = ["router"]
