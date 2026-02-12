from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from ade_api.api.deps import WriteSessionDep
from ade_api.features.admin_scim.service import ScimTokenService
from ade_api.features.admin_settings.service import RuntimeSettingsService
from ade_db.models import ScimToken

from .errors import ScimApiError

AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]


def _extract_bearer_token(value: str | None) -> str:
    if value is None:
        raise ScimApiError(status_code=401, detail="Missing bearer token")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ScimApiError(status_code=401, detail="Invalid bearer token")
    return token.strip()


def require_scim_auth(
    authorization: AuthorizationHeader,
    session: WriteSessionDep,
) -> ScimToken:
    mode = (
        RuntimeSettingsService(session=session)
        .get_effective_values()
        .auth.identity_provider.provisioning_mode
    )
    if mode != "scim":
        raise ScimApiError(status_code=404, detail="SCIM endpoint not enabled")
    token = _extract_bearer_token(authorization)
    try:
        return ScimTokenService(session=session).authenticate_bearer_token(token=token)
    except HTTPException as exc:
        raise ScimApiError(status_code=exc.status_code, detail=str(exc.detail)) from exc


ScimAuthDep = Annotated[ScimToken, Depends(require_scim_auth)]


__all__ = ["ScimAuthDep", "require_scim_auth"]
