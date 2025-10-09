"""Security dependencies for FastAPI routers."""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import SecurityScopes

from app.api.deps import SessionDependency
from app.api.settings import get_app_settings
from app.core.config import Settings
from app.features.auth.dependencies import get_current_identity, get_current_user
from app.features.auth.service import AuthService, AuthenticatedIdentity
from app.features.roles.authorization import authorize
from app.features.users.models import User


async def require_authenticated(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Ensure the request is associated with an authenticated user."""

    return user


async def require_csrf(
    request: Request,
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    session: SessionDependency,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> None:
    """Enforce CSRF validation for mutating requests."""

    if identity.credentials != "session_cookie":
        return

    service = AuthService(session=session, settings=settings)
    access_payload, _ = service.extract_session_payloads(
        request, include_refresh=False
    )
    service.enforce_csrf(request, access_payload)


def forbidden_response(
    *, permission: str, scope_type: str, scope_id: str | None
) -> HTTPException:
    detail = {
        "error": "forbidden",
        "permission": permission,
        "scope_type": scope_type,
        "scope_id": scope_id,
    }
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


def require_global(
    permission: str,
) -> Callable[[SecurityScopes, AuthenticatedIdentity, SessionDependency], User]:
    """Return a dependency that enforces a global permission."""

    async def dependency(
        _security_scopes: SecurityScopes,
        identity: Annotated[
            AuthenticatedIdentity, Depends(get_current_identity)
        ],
        session: SessionDependency,
    ) -> User:
        decision = await authorize(
            session=session,
            principal_id=str(identity.principal.id),
            permission_key=permission,
            scope_type="global",
        )
        if not decision.is_authorized:
            raise forbidden_response(
                permission=permission,
                scope_type="global",
                scope_id=None,
            )
        return identity.user

    return dependency


def _resolve_workspace_param(
    *,
    request: Request,
    security_scopes: SecurityScopes,
    default: str,
    permission: str,
) -> str:
    param_name = default
    for scope in security_scopes.scopes:
        if scope.startswith("{") and scope.endswith("}") and len(scope) > 2:
            param_name = scope[1:-1]
            break

    workspace_id = request.path_params.get(param_name) or request.query_params.get(
        param_name
    )
    if not workspace_id:
        detail = {
            "error": "invalid_scope",
            "permission": permission,
            "scope_type": "workspace",
            "scope_param": param_name,
            "message": f"Workspace scope parameter '{param_name}' is required.",
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    return str(workspace_id)


def require_workspace(
    permission: str, *, scope_param: str = "workspace_id"
) -> Callable[
    [Request, SecurityScopes, AuthenticatedIdentity, SessionDependency], User
]:
    """Return a dependency that enforces a workspace-scoped permission."""

    async def dependency(
        request: Request,
        security_scopes: SecurityScopes,
        identity: Annotated[
            AuthenticatedIdentity, Depends(get_current_identity)
        ],
        session: SessionDependency,
    ) -> User:
        workspace_id = _resolve_workspace_param(
            request=request,
            security_scopes=security_scopes,
            default=scope_param,
            permission=permission,
        )
        decision = await authorize(
            session=session,
            principal_id=str(identity.principal.id),
            permission_key=permission,
            scope_type="workspace",
            scope_id=workspace_id,
        )
        if not decision.is_authorized:
            raise forbidden_response(
                permission=permission,
                scope_type="workspace",
                scope_id=workspace_id,
            )
        return identity.user

    return dependency


def require_permissions_catalog_access(
    *,
    global_permission: str = "Roles.Read.All",
    workspace_permission: str = "Workspace.Roles.Read",
    workspace_param: str = "workspace_id",
) -> Callable[
    [
        Request,
        SecurityScopes,
        str,
        str | None,
        AuthenticatedIdentity,
        SessionDependency,
    ],
    User,
]:
    """Return a dependency that validates permission catalog access by scope."""

    async def dependency(
        request: Request,
        security_scopes: SecurityScopes,
        scope: str,
        identity: Annotated[
            AuthenticatedIdentity, Depends(get_current_identity)
        ],
        session: SessionDependency,
        workspace_id: str | None = None,
    ) -> User:
        if scope == "global":
            decision = await authorize(
                session=session,
                principal_id=str(identity.principal.id),
                permission_key=global_permission,
                scope_type="global",
            )
            if not decision.is_authorized:
                raise forbidden_response(
                    permission=global_permission,
                    scope_type="global",
                    scope_id=None,
                )
            return identity.user

        if workspace_id is None:
            detail = {
                "error": "invalid_scope",
                "permission": workspace_permission,
                "scope_type": "workspace",
                "scope_param": workspace_param,
                "message": f"Workspace scope parameter '{workspace_param}' is required.",
            }
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

        decision = await authorize(
            session=session,
            principal_id=str(identity.principal.id),
            permission_key=workspace_permission,
            scope_type="workspace",
            scope_id=workspace_id,
        )
        if not decision.is_authorized:
            raise forbidden_response(
                permission=workspace_permission,
                scope_type="workspace",
                scope_id=workspace_id,
            )
        return identity.user

    return dependency


__all__ = [
    "require_authenticated",
    "require_csrf",
    "forbidden_response",
    "require_global",
    "require_workspace",
    "require_permissions_catalog_access",
]
