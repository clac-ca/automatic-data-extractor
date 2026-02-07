"""FastAPI router for API key management."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, Security, status

from ade_api.api.deps import get_api_keys_service, get_api_keys_service_read
from ade_api.common.concurrency import require_if_match
from ade_api.common.etag import build_etag_token, format_weak_etag
from ade_api.common.cursor_listing import (
    CursorPage,
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    strict_cursor_query_guard,
)
from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.http import get_current_principal, require_csrf, require_global
from ade_db.models import ApiKey

from .schemas import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyPage, ApiKeySummary
from .service import ApiKeyAccessDeniedError, ApiKeyNotFoundError, ApiKeyService
from .sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(tags=["api-keys"])

UserPath = Annotated[
    UUID,
    Path(
        description="User identifier",
        alias="userId",
    ),
]
ApiKeyPath = Annotated[
    UUID,
    Path(
        description="API key identifier",
        alias="apiKeyId",
    ),
]
TenantUserIdQuery = Annotated[
    UUID | None,
    Query(
        alias="userId",
        description="Optional user identifier filter.",
    ),
]
ApiKeysServiceDep = Annotated[ApiKeyService, Depends(get_api_keys_service)]
ApiKeysServiceReadDep = Annotated[ApiKeyService, Depends(get_api_keys_service_read)]


def _serialize_summary(record: ApiKey) -> ApiKeySummary:
    return ApiKeySummary(
        id=record.id,
        user_id=record.user_id,
        prefix=record.prefix,
        name=record.name,
        created_at=record.created_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
        last_used_at=getattr(record, "last_used_at", None),
    )


def _make_create_response(result) -> ApiKeyCreateResponse:
    api_key = result.api_key
    return ApiKeyCreateResponse(
        id=api_key.id,
        user_id=api_key.user_id,
        secret=result.secret,
        prefix=api_key.prefix,
        name=api_key.name,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


def _map_page(page: CursorPage[ApiKey]) -> ApiKeyPage:
    summaries = [_serialize_summary(record) for record in page.items]
    return ApiKeyPage(
        items=summaries,
        meta=page.meta,
        facets=page.facets,
    )


def _api_key_etag_token(record: ApiKey) -> str:
    return build_etag_token(record.id, record.revoked_at or record.created_at)


# ---------------------------------------------------------------------------
# Tenant admin: /apikeys
# ---------------------------------------------------------------------------


@router.get(
    "/apikeys",
    response_model=ApiKeyPage,
    summary="List API keys across the tenant (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {"description": "Requires api_keys.read_all global permission."},
    },
)
def list_api_keys(
    _: Annotated[None, Security(require_global("api_keys.read_all"))],
    service: ApiKeysServiceReadDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard(allowed_extra={"userId"}))],
    user_id: TenantUserIdQuery = None,
) -> ApiKeyPage:
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result_page = service.list_all(
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        user_id=user_id,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )
    return _map_page(result_page)


# ---------------------------------------------------------------------------
# Self-service: /users/me/apikeys
# ---------------------------------------------------------------------------


@router.get(
    "/users/me/apikeys",
    response_model=ApiKeyPage,
    summary="List API keys for the current user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
    },
)
def list_my_api_keys(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: ApiKeysServiceReadDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
) -> ApiKeyPage:
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result_page = service.list_for_user(
        user_id=principal.user_id,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )

    return _map_page(result_page)


@router.post(
    "/users/me/apikeys",
    dependencies=[Security(require_csrf)],
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key for the current user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid API key payload."},
    },
)
def create_my_api_key(
    payload: ApiKeyCreateRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: ApiKeysServiceDep,
) -> ApiKeyCreateResponse:
    try:
        result = service.create_for_user(
            user_id=principal.user_id,
            name=payload.name,
            expires_in_days=payload.expires_in_days,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _make_create_response(result)


@router.get(
    "/users/me/apikeys/{apiKeyId}",
    response_model=ApiKeySummary,
    summary="Retrieve one of the current user's API keys",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "API key not found."},
        status.HTTP_403_FORBIDDEN: {"description": "API key not owned by caller."},
    },
)
def read_my_api_key(
    api_key_id: ApiKeyPath,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: ApiKeysServiceReadDep,
    response: Response,
) -> ApiKeySummary:
    try:
        record = service.get_by_id(api_key_id)
    except ApiKeyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if record.user_id != principal.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="API key not owned by caller.")

    etag = format_weak_etag(_api_key_etag_token(record))
    if etag:
        response.headers["ETag"] = etag
    return _serialize_summary(record)


@router.delete(
    "/users/me/apikeys/{apiKeyId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke one of the current user's API keys",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "API key not found."},
        status.HTTP_403_FORBIDDEN: {"description": "API key not owned by caller."},
    },
)
def revoke_my_api_key(
    api_key_id: ApiKeyPath,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: ApiKeysServiceDep,
    request: Request,
) -> Response:
    try:
        record = service.get_by_id(api_key_id)
        if record.user_id != principal.user_id:
            raise ApiKeyAccessDeniedError(
                f"API key {api_key_id} is not owned by user {principal.user_id}"
            )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=_api_key_etag_token(record),
        )
        service.revoke_for_user(
            api_key_id=api_key_id,
            user_id=principal.user_id,
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
# Admin: per-user /users/{userId}/apikeys
# ---------------------------------------------------------------------------


@router.get(
    "/users/{userId}/apikeys",
    response_model=ApiKeyPage,
    summary="List API keys for a specific user (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {"description": "Requires api_keys.read_all global permission."},
    },
)
def list_user_api_keys(
    user_id: UserPath,
    _: Annotated[None, Security(require_global("api_keys.read_all"))],
    service: ApiKeysServiceReadDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
) -> ApiKeyPage:
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result_page = service.list_for_user(
        user_id=user_id,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )
    return _map_page(result_page)


@router.get(
    "/users/{userId}/apikeys/{apiKeyId}",
    response_model=ApiKeySummary,
    summary="Retrieve an API key for a specific user (admin)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {"description": "Requires api_keys.read_all global permission."},
        status.HTTP_404_NOT_FOUND: {"description": "API key not found."},
    },
)
def read_user_api_key(
    user_id: UserPath,
    api_key_id: ApiKeyPath,
    _: Annotated[None, Security(require_global("api_keys.read_all"))],
    service: ApiKeysServiceReadDep,
    response: Response,
) -> ApiKeySummary:
    try:
        record = service.get_by_id(api_key_id)
    except ApiKeyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if record.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")

    etag = format_weak_etag(_api_key_etag_token(record))
    if etag:
        response.headers["ETag"] = etag
    return _serialize_summary(record)


@router.post(
    "/users/{userId}/apikeys",
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
def create_user_api_key(
    user_id: UserPath,
    payload: ApiKeyCreateRequest,
    _: Annotated[None, Security(require_global("api_keys.manage_all"))],
    service: ApiKeysServiceDep,
) -> ApiKeyCreateResponse:
    try:
        result = service.create_for_user(
            user_id=user_id,
            name=payload.name,
            expires_in_days=payload.expires_in_days,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _make_create_response(result)


@router.delete(
    "/users/{userId}/apikeys/{apiKeyId}",
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
def revoke_user_api_key(
    user_id: UserPath,
    api_key_id: ApiKeyPath,
    _: Annotated[None, Security(require_global("api_keys.manage_all"))],
    service: ApiKeysServiceDep,
    request: Request,
) -> Response:
    try:
        record = service.get_by_id(api_key_id)
        if record.user_id != user_id:
            raise ApiKeyAccessDeniedError("API key not found")
        require_if_match(
            request.headers.get("if-match"),
            expected_token=_api_key_etag_token(record),
        )
        service.revoke_for_user(
            api_key_id=api_key_id,
            user_id=user_id,
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
