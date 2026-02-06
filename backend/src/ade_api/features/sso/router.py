"""Admin routes for SSO provider management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Response, Security, status

from ade_api.api.deps import get_sso_service, get_sso_service_read
from ade_api.core.http import require_authenticated, require_csrf, require_global
from ade_db.models import SsoProvider

from .schemas import (
    SsoProviderAdminOut,
    SsoProviderCreate,
    SsoProviderListResponse,
    SsoProviderUpdate,
    SsoSettings,
)
from .service import SsoService

router = APIRouter(
    prefix="/admin/sso",
    tags=["sso"],
    dependencies=[Security(require_authenticated)],
)

PROVIDER_ID_PARAM = Annotated[str, Path(description="Provider identifier.", alias="id")]
PROVIDER_CREATE_BODY = Body(..., description="SSO provider to create.")
PROVIDER_UPDATE_BODY = Body(..., description="SSO provider fields to update.")


def _serialize_provider(provider: SsoProvider) -> SsoProviderAdminOut:
    domains = sorted([domain.domain for domain in provider.domains])
    return SsoProviderAdminOut(
        id=provider.id,
        type=provider.type,
        label=provider.label,
        issuer=provider.issuer,
        client_id=provider.client_id,
        status=provider.status,
        domains=domains,
        managed_by=provider.managed_by,
        locked=provider.locked,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.get(
    "/providers",
    response_model=SsoProviderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List SSO providers (admin)",
    response_model_exclude_none=True,
)
def list_providers(
    _: Annotated[object, Security(require_global("system.settings.read"))],
    service: Annotated[SsoService, Depends(get_sso_service_read)],
) -> SsoProviderListResponse:
    providers = [_serialize_provider(provider) for provider in service.list_providers()]
    return SsoProviderListResponse(items=providers)


@router.post(
    "/providers",
    dependencies=[Security(require_csrf)],
    response_model=SsoProviderAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an SSO provider (admin)",
    response_model_exclude_none=True,
)
def create_provider(
    _: Annotated[object, Security(require_global("system.settings.manage"))],
    service: Annotated[SsoService, Depends(get_sso_service)],
    payload: SsoProviderCreate = PROVIDER_CREATE_BODY,
) -> SsoProviderAdminOut:
    provider = service.create_provider(
        provider_id=payload.id,
        label=payload.label,
        issuer=payload.issuer,
        client_id=payload.client_id,
        client_secret=payload.client_secret.get_secret_value(),
        status_value=payload.status,
        domains=payload.domains,
    )
    return _serialize_provider(provider)


@router.get(
    "/providers/{id}",
    response_model=SsoProviderAdminOut,
    status_code=status.HTTP_200_OK,
    summary="Get an SSO provider (admin)",
    response_model_exclude_none=True,
)
def get_provider(
    _: Annotated[object, Security(require_global("system.settings.read"))],
    provider_id: PROVIDER_ID_PARAM,
    service: Annotated[SsoService, Depends(get_sso_service_read)],
) -> SsoProviderAdminOut:
    provider = service.get_provider(provider_id)
    return _serialize_provider(provider)


@router.patch(
    "/providers/{id}",
    dependencies=[Security(require_csrf)],
    response_model=SsoProviderAdminOut,
    status_code=status.HTTP_200_OK,
    summary="Update an SSO provider (admin)",
    response_model_exclude_none=True,
)
def update_provider(
    _: Annotated[object, Security(require_global("system.settings.manage"))],
    provider_id: PROVIDER_ID_PARAM,
    service: Annotated[SsoService, Depends(get_sso_service)],
    payload: SsoProviderUpdate = PROVIDER_UPDATE_BODY,
) -> SsoProviderAdminOut:
    provider = service.update_provider(
        provider_id,
        label=payload.label,
        issuer=payload.issuer,
        client_id=payload.client_id,
        client_secret=payload.client_secret.get_secret_value()
        if payload.client_secret
        else None,
        status_value=payload.status,
        domains=payload.domains,
    )
    return _serialize_provider(provider)


@router.delete(
    "/providers/{id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disable an SSO provider (admin)",
)
def delete_provider(
    _: Annotated[object, Security(require_global("system.settings.manage"))],
    provider_id: PROVIDER_ID_PARAM,
    service: Annotated[SsoService, Depends(get_sso_service)],
) -> Response:
    service.delete_provider(provider_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/settings",
    response_model=SsoSettings,
    status_code=status.HTTP_200_OK,
    summary="Read SSO global settings (admin)",
    response_model_exclude_none=True,
)
def read_sso_settings(
    _: Annotated[object, Security(require_global("system.settings.read"))],
    service: Annotated[SsoService, Depends(get_sso_service)],
) -> SsoSettings:
    return SsoSettings(enabled=service.is_sso_enabled())


@router.put(
    "/settings",
    dependencies=[Security(require_csrf)],
    response_model=SsoSettings,
    status_code=status.HTTP_200_OK,
    summary="Update SSO global settings (admin)",
    response_model_exclude_none=True,
)
def update_sso_settings(
    _: Annotated[object, Security(require_global("system.settings.manage"))],
    service: Annotated[SsoService, Depends(get_sso_service)],
    payload: SsoSettings = Body(..., description="SSO global settings."),
) -> SsoSettings:
    enabled = service.set_sso_enabled(enabled=payload.enabled)
    return SsoSettings(enabled=enabled)


__all__ = ["router"]
