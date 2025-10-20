"""FastAPI dependencies for role-based authorization checks."""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, Request
from fastapi.security import SecurityScopes
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.features.auth.dependencies import get_current_identity
from backend.app.features.auth.service import AuthenticatedIdentity
from backend.app.features.roles.authorization import authorize
from backend.app.features.users.models import User
from backend.app.platform.security import forbidden_response, resolve_workspace_scope


def require_global(
    permission: str,
) -> Callable[[SecurityScopes, AuthenticatedIdentity, AsyncSession], User]:
    """Return a dependency that enforces a global permission."""

    async def dependency(
        _security_scopes: SecurityScopes,
        identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
        session: Annotated[AsyncSession, Depends(get_session)],
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


def require_workspace(
    permission: str, *, scope_param: str = "workspace_id"
) -> Callable[[Request, SecurityScopes, AuthenticatedIdentity, AsyncSession], User]:
    """Return a dependency that enforces a workspace-scoped permission."""

    async def dependency(
        request: Request,
        security_scopes: SecurityScopes,
        identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> User:
        workspace_id = resolve_workspace_scope(
            request=request,
            security_scopes=security_scopes,
            default_param=scope_param,
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
) -> Callable[[Request, SecurityScopes, str, str | None, AuthenticatedIdentity, AsyncSession], User]:
    """Return a dependency that validates permission catalog access by scope."""

    async def dependency(
        request: Request,
        security_scopes: SecurityScopes,
        scope: str,
        identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
        session: Annotated[AsyncSession, Depends(get_session)],
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

        candidate = workspace_id or resolve_workspace_scope(
            request=request,
            security_scopes=security_scopes,
            default_param=workspace_param,
            permission=workspace_permission,
        )
        decision = await authorize(
            session=session,
            principal_id=str(identity.principal.id),
            permission_key=workspace_permission,
            scope_type="workspace",
            scope_id=candidate,
        )
        if not decision.is_authorized:
            raise forbidden_response(
                permission=workspace_permission,
                scope_type="workspace",
                scope_id=candidate,
            )
        return identity.user

    return dependency


__all__ = [
    "require_global",
    "require_workspace",
    "require_permissions_catalog_access",
]
