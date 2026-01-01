from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.http import get_current_principal, get_rbac_service, require_csrf
from ade_api.core.http.csrf import set_csrf_cookie
from ade_api.core.rbac.service_interface import RbacService
from ade_api.db import get_db_session
from ade_api.settings import Settings, get_settings

from .schemas import (
    EffectivePermissions,
    MeContext,
    MeProfile,
    PermissionCheckRequest,
    PermissionCheckResponse,
)
from .service import MeService

router = APIRouter(
    prefix="/me",
    tags=["me"],
)


def get_me_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    rbac: Annotated[RbacService, Depends(get_rbac_service)],
) -> MeService:
    """Per-request MeService factory."""

    return MeService(session=session, rbac=rbac)


@router.get(
    "",
    response_model=MeProfile,
    status_code=status.HTTP_200_OK,
    summary="Return the authenticated user's profile",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access the profile."
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Service account principals cannot access this endpoint."
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "User record not found.",
        },
    },
)
async def get_me(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[MeService, Depends(get_me_service)],
) -> MeProfile:
    """Return the current principal's profile."""

    return await service.get_profile(principal)


@router.get(
    "/bootstrap",
    response_model=MeContext,
    status_code=status.HTTP_200_OK,
    summary="Bootstrap the session with profile, roles, permissions, and workspaces",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to bootstrap the session."
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Service account principals cannot access this endpoint."
        },
    },
)
async def get_me_bootstrap(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[MeService, Depends(get_me_service)],
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeContext:
    """Return a consolidated bootstrap payload for the current principal."""

    set_csrf_cookie(response, settings)
    return await service.get_context(
        principal,
    )


@router.get(
    "/permissions",
    response_model=EffectivePermissions,
    status_code=status.HTTP_200_OK,
    summary="Return the caller's effective global and workspace permissions",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to inspect permissions."
        },
    },
)
async def get_me_permissions(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[MeService, Depends(get_me_service)],
) -> EffectivePermissions:
    """Return the effective permissions for the current principal."""

    return await service.get_effective_permissions(principal=principal)


@router.post(
    "/permissions/check",
    response_model=PermissionCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check whether the caller has specific permissions",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to evaluate permissions."
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found when scoped permissions are requested."
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid permission keys or missing workspace identifier."
        },
    },
)
async def check_permissions(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[MeService, Depends(get_me_service)],
    payload: PermissionCheckRequest,
) -> PermissionCheckResponse:
    """Evaluate a set of permission keys for the current principal."""

    return await service.check_permissions(
        principal=principal,
        payload=payload,
    )
