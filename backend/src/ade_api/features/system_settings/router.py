"""API routes for system settings controls."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, Security, status

from ade_api.api.deps import get_safe_mode_service, get_safe_mode_service_read
from ade_api.core.http import require_authenticated, require_csrf, require_global

from .schemas import SafeModeStatus, SafeModeUpdateRequest
from .service import SafeModeService

router = APIRouter(
    prefix="/system",
    tags=["system"],
    dependencies=[Security(require_authenticated)],
)


@router.get(
    "/safemode",
    response_model=SafeModeStatus,
    status_code=status.HTTP_200_OK,
    summary="Read ADE safe mode status",
)
def read_safe_mode(
    service: Annotated[SafeModeService, Depends(get_safe_mode_service_read)],
    _actor: Annotated[object, Security(require_global("system.settings.read"))],
) -> SafeModeStatus:
    """Return the current ADE safe mode status."""

    return service.get_status()


@router.put(
    "/safemode",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Toggle ADE safe mode",
    dependencies=[Security(require_csrf)],
)
def update_safe_mode(
    payload: SafeModeUpdateRequest,
    service: Annotated[SafeModeService, Depends(get_safe_mode_service)],
    _actor: Annotated[object, Security(require_global("system.settings.manage"))],
) -> Response:
    """Persist and broadcast an updated ADE safe mode state."""

    service.update_status(
        enabled=payload.enabled,
        detail=payload.detail,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
