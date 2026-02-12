from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, Query, Response, status
from starlette.responses import JSONResponse

from ade_api.api.deps import WriteSessionDep

from .deps import ScimAuthDep
from .service import ScimProvisioningService

router = APIRouter(prefix="/scim/v2", tags=["scim"])


def _scim_json(payload: dict[str, Any], *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload, media_type="application/scim+json"
    )


def _service(session: WriteSessionDep) -> ScimProvisioningService:
    return ScimProvisioningService(session=session)


StartIndexQuery = Annotated[int, Query(alias="startIndex", ge=1, le=10_000)]
CountQuery = Annotated[int, Query(alias="count", ge=1, le=1_000)]
ScimUserPath = Annotated[UUID, Path(alias="userId", description="SCIM user identifier")]
ScimGroupPath = Annotated[UUID, Path(alias="groupId", description="SCIM group identifier")]


@router.get("/ServiceProviderConfig", summary="SCIM service provider configuration")
def get_service_provider_config(
    _auth: ScimAuthDep,
) -> JSONResponse:
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": False},
        "filter": {"supported": True, "maxResults": 1000},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Use a bearer token issued by ADE admin settings.",
                "specUri": "https://datatracker.ietf.org/doc/html/rfc6750",
                "primary": True,
            }
        ],
    }
    return _scim_json(payload)


@router.get("/Schemas", summary="SCIM schema list")
def list_schemas(
    _auth: ScimAuthDep,
) -> JSONResponse:
    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 3,
        "startIndex": 1,
        "itemsPerPage": 3,
        "Resources": [
            {
                "id": "urn:ietf:params:scim:schemas:core:2.0:User",
                "name": "User",
                "description": "User Account",
            },
            {
                "id": "urn:ietf:params:scim:schemas:core:2.0:Group",
                "name": "Group",
                "description": "Group",
            },
            {
                "id": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                "name": "EnterpriseUser",
                "description": "Enterprise User",
            },
        ],
    }
    return _scim_json(payload)


@router.get("/ResourceTypes", summary="SCIM resource type list")
def list_resource_types(
    _auth: ScimAuthDep,
) -> JSONResponse:
    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 2,
        "startIndex": 1,
        "itemsPerPage": 2,
        "Resources": [
            {
                "id": "User",
                "name": "User",
                "endpoint": "/Users",
                "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
                "schemaExtensions": [
                    {
                        "schema": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                        "required": False,
                    }
                ],
            },
            {
                "id": "Group",
                "name": "Group",
                "endpoint": "/Groups",
                "schema": "urn:ietf:params:scim:schemas:core:2.0:Group",
            },
        ],
    }
    return _scim_json(payload)


@router.get("/Users", summary="List SCIM users")
def list_users(
    _auth: ScimAuthDep,
    session: WriteSessionDep,
    filter_value: str | None = Query(default=None, alias="filter"),
    start_index: StartIndexQuery = 1,
    count: CountQuery = 100,
) -> JSONResponse:
    payload = _service(session).list_users(
        filter_value=filter_value,
        start_index=start_index,
        count=count,
    )
    return _scim_json(payload)


@router.post("/Users", summary="Create SCIM user", status_code=status.HTTP_201_CREATED)
def create_user(
    body: dict[str, Any],
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).create_user(payload=body)
    return _scim_json(payload, status_code=status.HTTP_201_CREATED)


@router.get("/Users/{userId}", summary="Get SCIM user")
def get_user(
    user_id: ScimUserPath,
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).get_user(user_id=user_id)
    return _scim_json(payload)


@router.put("/Users/{userId}", summary="Replace SCIM user")
def replace_user(
    user_id: ScimUserPath,
    body: dict[str, Any],
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).replace_user(user_id=user_id, payload=body)
    return _scim_json(payload)


@router.patch("/Users/{userId}", summary="Patch SCIM user")
def patch_user(
    user_id: ScimUserPath,
    body: dict[str, Any],
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).patch_user(user_id=user_id, payload=body)
    return _scim_json(payload)


@router.get("/Groups", summary="List SCIM groups")
def list_groups(
    _auth: ScimAuthDep,
    session: WriteSessionDep,
    filter_value: str | None = Query(default=None, alias="filter"),
    start_index: StartIndexQuery = 1,
    count: CountQuery = 100,
) -> JSONResponse:
    payload = _service(session).list_groups(
        filter_value=filter_value,
        start_index=start_index,
        count=count,
    )
    return _scim_json(payload)


@router.post("/Groups", summary="Create SCIM group", status_code=status.HTTP_201_CREATED)
def create_group(
    body: dict[str, Any],
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).create_group(payload=body)
    return _scim_json(payload, status_code=status.HTTP_201_CREATED)


@router.get("/Groups/{groupId}", summary="Get SCIM group")
def get_group(
    group_id: ScimGroupPath,
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).get_group(group_id=group_id)
    return _scim_json(payload)


@router.put("/Groups/{groupId}", summary="Replace SCIM group")
def replace_group(
    group_id: ScimGroupPath,
    body: dict[str, Any],
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).replace_group(group_id=group_id, payload=body)
    return _scim_json(payload)


@router.patch("/Groups/{groupId}", summary="Patch SCIM group")
def patch_group(
    group_id: ScimGroupPath,
    body: dict[str, Any],
    _auth: ScimAuthDep,
    session: WriteSessionDep,
) -> JSONResponse:
    payload = _service(session).patch_group(group_id=group_id, payload=body)
    return _scim_json(payload)


@router.head("/ServiceProviderConfig", include_in_schema=False)
def head_service_provider_config(_auth: ScimAuthDep) -> Response:
    return Response(status_code=status.HTTP_200_OK, media_type="application/scim+json")


__all__ = ["router"]
