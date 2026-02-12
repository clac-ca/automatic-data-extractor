"""Graph-style batch endpoint for access-management user operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status

from ade_api.api.deps import SettingsDep, WriteSessionDep
from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.http import (
    get_current_principal,
    get_rbac_service,
    require_authenticated,
    require_csrf,
)
from ade_api.core.rbac.service_interface import RbacService as RbacServiceInterface
from ade_db.models import User

from .schemas import BatchRequest, BatchResponse
from .service import BatchService

router = APIRouter(tags=["users"], dependencies=[Security(require_authenticated)])


@router.post(
    "/$batch",
    dependencies=[Security(require_csrf)],
    response_model=BatchResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Execute user lifecycle mutations in batch",
)
def execute_user_batch(
    actor: Annotated[User, Security(require_authenticated)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    rbac: Annotated[RbacServiceInterface, Depends(get_rbac_service)],
    session: WriteSessionDep,
    settings: SettingsDep,
    payload: BatchRequest,
) -> BatchResponse:
    service = BatchService(
        session=session,
        settings=settings,
        actor=actor,
        principal=principal,
        rbac=rbac,
    )
    return service.execute(payload)


__all__ = ["router"]
