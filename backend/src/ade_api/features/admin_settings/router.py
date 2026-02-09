"""Unified admin endpoints for runtime settings."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status

from ade_api.api.deps import get_runtime_settings_service, get_runtime_settings_service_read
from ade_api.core.http import require_authenticated, require_csrf, require_global
from ade_db.models import User

from .schemas import AdminSettingsPatchRequest, AdminSettingsReadResponse
from .service import RuntimeSettingsService

router = APIRouter(
    prefix="/admin/settings",
    tags=["admin-settings"],
    dependencies=[Security(require_authenticated)],
)


@router.get(
    "",
    response_model=AdminSettingsReadResponse,
    status_code=status.HTTP_200_OK,
    summary="Read runtime admin settings",
)
def read_admin_settings(
    service: Annotated[RuntimeSettingsService, Depends(get_runtime_settings_service_read)],
    _actor: Annotated[User, Security(require_global("system.settings.read"))],
) -> AdminSettingsReadResponse:
    return service.read()


@router.patch(
    "",
    response_model=AdminSettingsReadResponse,
    status_code=status.HTTP_200_OK,
    summary="Update runtime admin settings",
    dependencies=[Security(require_csrf)],
)
def patch_admin_settings(
    payload: AdminSettingsPatchRequest,
    service: Annotated[RuntimeSettingsService, Depends(get_runtime_settings_service)],
    actor: Annotated[User, Security(require_global("system.settings.manage"))],
) -> AdminSettingsReadResponse:
    return service.update(payload=payload, updated_by=actor.id)


__all__ = ["router"]
