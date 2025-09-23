"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import HealthResponse
from ..services.maintenance_status import get_auto_purge_status

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    openapi_extra={"security": []},
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Return service health and validate the database connection."""

    db.execute(text("SELECT 1")).scalar_one()
    purge_status = get_auto_purge_status(db)
    return HealthResponse(status="ok", purge=purge_status)


__all__ = ["router", "health_check"]
