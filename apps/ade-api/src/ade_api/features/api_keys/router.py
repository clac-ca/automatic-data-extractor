"""FastAPI router for API key management."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Security, status

from ade_api.app.dependencies import get_api_keys_service
from ade_api.common.pagination import Page as GenericPage
from ade_api.common.pagination import PageParams
from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.http import get_current_principal, require_csrf, require_global
from ade_api.core.models import ApiKey

from .schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyIssueRequest,
    ApiKeyPage,
    ApiKeySummary,
)
from .service import (
    ApiKeyAccessDeniedError,
    ApiKeyNotFoundError,
    ApiKeyService,
)

router = APIRouter(tags=["api-keys"])


def _serialize_summary(record: ApiKey) -> ApiKeySummary:
    return ApiKeySummary(
        id=record.id,
        owner_user_id=record.owner_user_id,
        created_by_user_id=record.created_by_user_id,
        token_prefix=record.token_prefix,
        label=record.label,
        scope_type=record.scope_type,
        scope_id=record.scope_id,
        created_at=record.created_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
        last_used_at=getattr(record, "last_used_at", None),
    )


def _make_create_response(result) -> ApiKeyCreateResponse:
    api_key = result.api_key
    return ApiKeyCreateResponse(
        id=api_key.id,
        owner_user_id=api_key.owner_user_id,
        created_by_user_id=api_key.created_by_user_id,
        secret=result.secret,
        token_prefix=api_key.token_prefix,
        label=api_key.label,
        scope_type=api_key.scope_type,
        scope_id=api_key.scope_id,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


def _map_page(page: GenericPage[ApiKey]) -> ApiKeyPage:
    summaries = [_serialize_summary(record) for record in page.items]
    return ApiKeyPage(
        items=summaries,
        page=page.page,
        page_size=page.page_size,
        has_next=page.has_next,
        has_previous=page.has_previous,
        total=page.total,
    )


# ---------------------------------------------------------------------------
# Self-service: /me/api-keys
# ---------------------------------------------------------------------------


@router.get(
    "/me/api-keys",
    response_model=ApiKeyPage,
    summary="List API keys for the current user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
    },
)
async def list_my_api_keys(
    principal: Annotated[AuthenticatedPrincipal, Security(get_current_principal)],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
    page: Annotated[PageParams, Depends()],
    include_revoked: Annotated[
        bool,
        Query(
            description="Include revoked keys in the response.",
        ),
    ] = False,
) -> ApiKeyPage:
    result_page = await service.list_for_owner(
        owner_user_id=principal.user_id,
        include_revoked=include_revoked,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )

    return _map_page(result_page)


@router.post(
    "/me/api-keys",
    dependencies=[Security(require_csrf)],
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key for the current user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid API key payload."},
    },
)
async def create_my_api_key(
    payload: ApiKeyCreateRequest,
    principal: Annotated[AuthenticatedPrincipal, Security(get_current_principal)],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
) -> ApiKeyCreateResponse:
    try:
        result = await service.create_for_user(
            owner_user_id=principal.user_id,
            created_by_user_id=principal.user_id,
            label=payload.label,
            expires_in_days=payload.expires_in_days,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _make_create_response(result)


@router.delete(
    "/me/api-keys/{api_key_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke one of the current user's API keys",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "API key not found."},
        status.HTTP_403_FORBIDDEN: {"description": "API key not owned by caller."},
    },
)
async def revoke_my_api_key(
    api_key_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Security(get_current_principal)],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
) -> Response:
    try:
        await service.revoke_for_owner(
            api_key_id=api_key_id,
            owner_user_id=principal.user_id,
        )
    except ApiKeyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ApiKeyAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Admin: tenant-wide /api-keys
# ---------------------------------------------------------------------------


@router.get(
    "/api-keys",
    response_model=ApiKeyPage,
    summary="List API keys across the tenant (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Requires api_keys.read_all global permission."
        },
    },
)
async def list_api_keys(
    _: Annotated[None, Security(require_global("api_keys.read_all"))],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
    page: Annotated[PageParams, Depends()],
    include_revoked: Annotated[
        bool,
        Query(
            description="Include revoked keys in the response.",
        ),
    ] = False,
    owner_user_id: Annotated[
        UUID | None,
        Query(
            description="Optional filter by owner user id.",
        ),
    ] = None,
) -> ApiKeyPage:
    result_page = await service.list_all(
        include_revoked=include_revoked,
        owner_user_id=owner_user_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return _map_page(result_page)


@router.post(
    "/api-keys",
    dependencies=[Security(require_csrf)],
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key for a user (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Requires api_keys.manage_all global permission."
        },
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid API key payload."},
    },
)
async def create_api_key(
    payload: ApiKeyIssueRequest,
    principal: Annotated[AuthenticatedPrincipal, Security(get_current_principal)],
    _: Annotated[None, Security(require_global("api_keys.manage_all"))],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
) -> ApiKeyCreateResponse:
    try:
        result = await service.create_for_user(
            owner_user_id=payload.user_id,
            email=payload.email,
            created_by_user_id=principal.user_id,
            label=payload.label,
            expires_in_days=payload.expires_in_days,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _make_create_response(result)


@router.get(
    "/api-keys/{api_key_id}",
    response_model=ApiKeySummary,
    summary="Retrieve a single API key (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Requires api_keys.read_all global permission."
        },
        status.HTTP_404_NOT_FOUND: {"description": "API key not found."},
    },
)
async def get_api_key(
    api_key_id: UUID,
    _: Annotated[None, Security(require_global("api_keys.read_all"))],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
) -> ApiKeySummary:
    try:
        record = await service.get_by_id(api_key_id)
    except ApiKeyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _serialize_summary(record)


@router.delete(
    "/api-keys/{api_key_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Requires api_keys.manage_all global permission."
        },
        status.HTTP_404_NOT_FOUND: {"description": "API key not found."},
    },
)
async def revoke_api_key(
    api_key_id: UUID,
    _: Annotated[None, Security(require_global("api_keys.manage_all"))],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
) -> Response:
    try:
        await service.revoke(api_key_id)
    except ApiKeyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Admin: per-user /users/{user_id}/api-keys
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/api-keys",
    response_model=ApiKeyPage,
    summary="List API keys for a specific user (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Requires api_keys.read_all global permission."
        },
    },
)
async def list_user_api_keys(
    user_id: UUID,
    _: Annotated[None, Security(require_global("api_keys.read_all"))],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
    page: Annotated[PageParams, Depends()],
    include_revoked: Annotated[
        bool,
        Query(
            description="Include revoked keys in the response.",
        ),
    ] = False,
) -> ApiKeyPage:
    result_page = await service.list_for_owner(
        owner_user_id=user_id,
        include_revoked=include_revoked,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return _map_page(result_page)


@router.post(
    "/users/{user_id}/api-keys",
    dependencies=[Security(require_csrf)],
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key for a specific user (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Requires api_keys.manage_all global permission."
        },
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid API key payload."},
    },
)
async def create_user_api_key(
    user_id: UUID,
    payload: ApiKeyCreateRequest,
    principal: Annotated[AuthenticatedPrincipal, Security(get_current_principal)],
    _: Annotated[None, Security(require_global("api_keys.manage_all"))],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
) -> ApiKeyCreateResponse:
    try:
        result = await service.create_for_user(
            owner_user_id=user_id,
            created_by_user_id=principal.user_id,
            label=payload.label,
            expires_in_days=payload.expires_in_days,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _make_create_response(result)


@router.delete(
    "/users/{user_id}/api-keys/{api_key_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key for a specific user (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "Requires api_keys.manage_all global permission."
        },
        status.HTTP_404_NOT_FOUND: {"description": "API key not found."},
    },
)
async def revoke_user_api_key(
    user_id: UUID,
    api_key_id: UUID,
    _: Annotated[None, Security(require_global("api_keys.manage_all"))],
    service: Annotated[ApiKeyService, Depends(get_api_keys_service)],
) -> Response:
    try:
        await service.revoke_for_owner(
            api_key_id=api_key_id,
            owner_user_id=user_id,
        )
    except ApiKeyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ApiKeyAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        ) from None

    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
