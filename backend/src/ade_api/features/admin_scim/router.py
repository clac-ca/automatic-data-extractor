from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Security, status

from ade_api.api.deps import ReadSessionDep, WriteSessionDep
from ade_api.core.http import require_authenticated, require_csrf, require_global
from ade_db.models import User

from .schemas import (
    ScimTokenCreateRequest,
    ScimTokenCreateResponse,
    ScimTokenListResponse,
    ScimTokenOut,
)
from .service import ScimTokenService

router = APIRouter(
    prefix="/admin/scim",
    tags=["admin-scim"],
    dependencies=[Security(require_authenticated)],
)

TokenPath = Annotated[
    UUID,
    Path(description="SCIM token identifier", alias="tokenId"),
]


@router.get(
    "/tokens",
    response_model=ScimTokenListResponse,
    status_code=status.HTTP_200_OK,
    summary="List SCIM provisioning tokens",
)
def list_scim_tokens(
    _actor: Annotated[User, Security(require_global("system.settings.read"))],
    session: ReadSessionDep,
) -> ScimTokenListResponse:
    return ScimTokenService(session=session).list_tokens()


@router.post(
    "/tokens",
    response_model=ScimTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SCIM provisioning token",
    dependencies=[Security(require_csrf)],
)
def create_scim_token(
    payload: ScimTokenCreateRequest,
    actor: Annotated[User, Security(require_global("system.settings.manage"))],
    session: WriteSessionDep,
) -> ScimTokenCreateResponse:
    return ScimTokenService(session=session).create_token(payload=payload, actor=actor)


@router.post(
    "/tokens/{tokenId}/revoke",
    response_model=ScimTokenOut,
    status_code=status.HTTP_200_OK,
    summary="Revoke SCIM provisioning token",
    dependencies=[Security(require_csrf)],
)
def revoke_scim_token(
    token_id: TokenPath,
    _actor: Annotated[User, Security(require_global("system.settings.manage"))],
    session: WriteSessionDep,
) -> ScimTokenOut:
    return ScimTokenService(session=session).revoke_token(token_id=token_id)


__all__ = ["router"]
