"""FastAPI dependencies that bridge HTTP requests to the auth/RBAC foundation."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.db.session import get_session as get_db_session
from ade_api.models.user import User
from ade_api.settings import Settings, get_settings

from ..auth import (
    AuthenticatedPrincipal,
    AuthenticationError,
    PermissionDeniedError,
    authenticate_request,
)
from ..auth.pipeline import ApiKeyAuthenticator, SessionAuthenticator
from ..rbac.service_interface import RbacService as RbacServiceInterface

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

PermissionDependency = Callable[..., Awaitable[User]]

class _RbacAdapter(RbacServiceInterface):
    """Bridge the RBAC feature service to the interface expected by dependencies."""

    def __init__(self, *, session: AsyncSession):
        super().__init__(session=session)

        from ade_api.features.rbac.service import RbacService

        self._service = RbacService(session=session)

    async def _resolve_user(self, principal: AuthenticatedPrincipal) -> User:
        user = await self.session.get(User, principal.user_id)
        if user is None:
            raise AuthenticationError("Unknown principal")
        if not getattr(user, "is_active", True):
            raise AuthenticationError("User account is inactive.")
        return user

    async def sync_registry(self) -> None:
        await self._service.sync_registry()

    async def get_global_role_slugs(
        self,
        principal: AuthenticatedPrincipal,
    ) -> set[str]:
        user = await self._resolve_user(principal)
        result = await self._service.get_global_role_slugs_for_user(user=user)
        return set(result)

    async def get_global_permissions(
        self,
        principal: AuthenticatedPrincipal,
    ) -> set[str]:
        user = await self._resolve_user(principal)
        result = await self._service.get_global_permissions_for_user(user=user)
        return set(result)

    async def get_workspace_permissions(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID | None = None,
    ) -> set[str]:
        if workspace_id is None:
            return set()

        user = await self._resolve_user(principal)
        result = await self._service.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_id,
        )
        return set(result)

    async def get_effective_permissions(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID | None = None,
    ) -> set[str]:
        global_permissions = await self.get_global_permissions(principal=principal)
        if workspace_id is None:
            return global_permissions

        workspace_permissions = await self.get_workspace_permissions(
            principal=principal,
            workspace_id=workspace_id,
        )
        return global_permissions.union(workspace_permissions)

    async def has_permission(
        self,
        principal: AuthenticatedPrincipal,
        permission_key: str,
        workspace_id: UUID | None = None,
    ) -> bool:
        from ade_api.features.rbac.service import AuthorizationError

        try:
            user = await self._resolve_user(principal)
            decision = await self._service.authorize(
                user=user,
                permission_key=permission_key,
                workspace_id=workspace_id,
            )
            return not decision.missing
        except AuthenticationError:
            raise
        except AuthorizationError:
            return False
        except Exception:
            return False


def get_api_key_authenticator(
    db: SessionDep,
    settings: SettingsDep,
) -> ApiKeyAuthenticator:
    """Provide the API key authenticator."""

    from ade_api.features.api_keys.service import ApiKeyService

    return ApiKeyService(session=db, settings=settings)


def get_session_authenticator(
    db: SessionDep,
    settings: SettingsDep,
) -> SessionAuthenticator:
    """Authenticate bearer tokens issued by the auth feature."""

    from ade_api.features.auth.service import AuthService

    class _BearerSessionAuthenticator:
        async def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
            header = request.headers.get("authorization") or ""
            scheme, _, token = header.partition(" ")
            candidate = token.strip() if scheme.lower() == "bearer" else ""
            if not candidate:
                cookie_token = request.cookies.get(settings.session_cookie_name)
                candidate = (cookie_token or "").strip()
            if not candidate:
                return None

            service = AuthService(session=db, settings=settings)
            try:
                return await service.resolve_principal_from_access_token(candidate)
            except AuthenticationError:
                raise
            except Exception:
                return None

    return _BearerSessionAuthenticator()


def get_rbac_service(
    db: SessionDep,
) -> RbacServiceInterface:
    """Return the RBAC service implementation."""

    return _RbacAdapter(session=db)


async def get_current_principal(
    request: Request,
    db: SessionDep,
    settings: SettingsDep,
    api_key_service: Annotated[
        ApiKeyAuthenticator,
        Depends(get_api_key_authenticator),
    ],
    session_service: Annotated[
        SessionAuthenticator,
        Depends(get_session_authenticator),
    ],
) -> AuthenticatedPrincipal:
    """Authenticate the incoming request and return the current principal."""

    return await authenticate_request(
        request=request,
        _db=db,
        settings=settings,
        api_key_service=api_key_service,
        session_service=session_service,
    )


async def require_authenticated(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    db: SessionDep,
) -> User:
    """Ensure the request is authenticated and return the persisted user."""

    user = await db.get(User, principal.user_id)
    if user is None:
        raise AuthenticationError("Unknown principal")
    if not getattr(user, "is_active", True):
        raise AuthenticationError("User account is inactive.")
    return user


def require_permission(
    permission_key: str,
    *,
    workspace_param: str | None = None,
) -> PermissionDependency:
    """Return a dependency enforcing a specific permission."""

    async def dependency(
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
        db: SessionDep,
        rbac: Annotated[RbacServiceInterface, Depends(get_rbac_service)],
    ) -> User:
        workspace_id = None
        if workspace_param:
            candidate = request.path_params.get(workspace_param)
            if isinstance(candidate, str):
                try:
                    workspace_id = UUID(candidate)
                except ValueError:
                    workspace_id = None
            else:
                workspace_id = candidate
        allowed = await rbac.has_permission(
            principal=principal,
            permission_key=permission_key,
            workspace_id=workspace_id,
        )
        if not allowed:
            raise PermissionDeniedError(
                permission_key=permission_key,
                scope_type="workspace" if workspace_id else "global",
                scope_id=workspace_id,
            )
        user = await db.get(User, principal.user_id)
        if user is None:
            raise AuthenticationError("Unknown principal")
        return user

    return dependency


def require_global(permission_key: str) -> PermissionDependency:
    return require_permission(permission_key, workspace_param=None)


def require_workspace(
    permission_key: str, workspace_param: str = "workspace_id"
) -> PermissionDependency:
    return require_permission(permission_key, workspace_param=workspace_param)


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


async def require_csrf(
    request: Request,
    settings: SettingsDep,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    """Enforce double-submit CSRF protection for cookie-authenticated requests.

    CSRF is required when the browser automatically attaches the session cookie.
    Requests authenticated via bearer tokens or API keys skip this guard.
    """

    if request.method.upper() in _SAFE_METHODS:
        return

    auth_header = request.headers.get("authorization") or ""
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return

    if (request.headers.get("x-api-key") or "").strip():
        return

    session_cookie = (request.cookies.get(settings.session_cookie_name) or "").strip()
    if not session_cookie:
        return

    cookie_csrf = (request.cookies.get(settings.session_csrf_cookie_name) or "").strip()
    header_csrf = (csrf_token or "").strip()

    if not cookie_csrf or not header_csrf or not secrets.compare_digest(cookie_csrf, header_csrf):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "csrf_failed",
                "message": "CSRF token missing or invalid.",
            },
        )
