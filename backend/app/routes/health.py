"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Return service health and validate the database connection."""

    db.execute(text("SELECT 1")).scalar_one()
    return HealthResponse(status="ok")


__all__ = ["router", "health_check"]
