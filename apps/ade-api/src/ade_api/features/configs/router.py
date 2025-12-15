"""HTTP router composition for configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Security

from ade_api.core.http import require_authenticated

from .endpoints.configurations import router as configuration_endpoints
from .endpoints.files import router as file_endpoints

_AUTH_DEPENDENCIES = [Security(require_authenticated)]

router = APIRouter(prefix="/workspaces/{workspace_id}")
router.include_router(
    configuration_endpoints,
    tags=["configurations"],
    dependencies=_AUTH_DEPENDENCIES,
)
router.include_router(
    file_endpoints,
    tags=["configurations"],
    dependencies=_AUTH_DEPENDENCIES,
)

__all__ = ["router"]
