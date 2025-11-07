"""FastAPI dependencies for the health feature."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from apps.api.app.settings import Settings, get_settings

from .service import HealthService


def get_health_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthService:
    """Return a health service configured for the current request."""

    return HealthService(settings=settings)


__all__ = ["get_health_service"]
