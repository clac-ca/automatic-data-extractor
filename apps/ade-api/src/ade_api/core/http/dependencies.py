"""FastAPI dependencies that bridge HTTP requests to the auth/RBAC foundation."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.db.session import get_session as get_db_session
from ade_api.db.session import get_websocket_session
from ade_api.common.time import utc_now
from ade_api.models import AccessToken, User
from ade_api.settings import Settings, get_settings

from ..auth import (
    AuthenticatedPrincipal,
    AuthenticationError,
    PermissionDeniedError,
    authenticate_request,
)
from ..auth.principal import AuthVia, PrincipalType
from ..auth.pipeline import ApiKeyAuthenticator, BearerAuthenticator, CookieAuthenticator
from ..rbac.service_interface import RbacService as RbacServiceInterface
from ..security.tokens import decode_token

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
WebSocketSessionDep = Annotated[AsyncSession, Depends(get_websocket_session)]
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


def get_api_key_authenticator_websocket(
    db: WebSocketSessionDep,
    settings: SettingsDep,
) -> ApiKeyAuthenticator:
    """Provide the API key authenticator for WebSocket endpoints."""

    from ade_api.features.api_keys.service import ApiKeyService

    return ApiKeyService(session=db, settings=settings)


def get_cookie_authenticator(
    db: SessionDep,
    settings: SettingsDep,
) -> CookieAuthenticator:
    """Authenticate cookie session tokens against the access_tokens table."""

    class _CookieAuthenticator:
        async def authenticate(self, token: str) -> AuthenticatedPrincipal | None:
            candidate = (token or "").strip()
            if not candidate:
                return None

            stmt = select(AccessToken).where(AccessToken.token == candidate).limit(1)
            result = await db.execute(stmt)
            access_token = result.scalar_one_or_none()
            if access_token is None:
                return None

            now = utc_now()
            expires_at = access_token.expires_at
            if expires_at is None:
                expires_at = access_token.created_at + settings.session_access_ttl
            if expires_at <= now:
                await db.delete(access_token)
                await db.flush()
                return None

            user = await db.get(User, access_token.user_id)
            if user is None:
                return None

            principal_type = (
                PrincipalType.SERVICE_ACCOUNT if user.is_service_account else PrincipalType.USER
            )
            return AuthenticatedPrincipal(
                user_id=user.id,
                principal_type=principal_type,
                auth_via=AuthVia.SESSION,
                api_key_id=None,
            )

    return _CookieAuthenticator()


def get_bearer_authenticator(
    db: SessionDep,
    settings: SettingsDep,
) -> BearerAuthenticator:
    """Authenticate JWT bearer tokens for non-browser clients."""

    class _BearerAuthenticator:
        async def authenticate(self, token: str) -> AuthenticatedPrincipal | None:
            candidate = (token or "").strip()
            if not candidate:
                return None

            try:
                payload = decode_token(
                    token=candidate,
                    secret=settings.jwt_secret_value,
                    algorithms=[settings.jwt_algorithm],
                    audience=["fastapi-users:auth"],
                )
            except Exception:
                return None

            subject = str(payload.get("sub") or "").strip()
            if not subject:
                return None

            try:
                user_id = UUID(subject)
            except ValueError:
                return None

            user = await db.get(User, user_id)
            if user is None:
                return None

            principal_type = (
                PrincipalType.SERVICE_ACCOUNT if user.is_service_account else PrincipalType.USER
            )
            return AuthenticatedPrincipal(
                user_id=user.id,
                principal_type=principal_type,
                auth_via=AuthVia.BEARER,
                api_key_id=None,
            )

    return _BearerAuthenticator()


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
    cookie_service: Annotated[
        CookieAuthenticator,
        Depends(get_cookie_authenticator),
    ],
    bearer_service: Annotated[
        BearerAuthenticator,
        Depends(get_bearer_authenticator),
    ],
) -> AuthenticatedPrincipal:
    """Authenticate the incoming request and return the current principal."""

    return await authenticate_request(
        request=request,
        _db=db,
        settings=settings,
        api_key_service=api_key_service,
        cookie_service=cookie_service,
        bearer_service=bearer_service,
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
    permission_key: str, workspace_param: str = "workspaceId"
) -> PermissionDependency:
    return require_permission(permission_key, workspace_param=workspace_param)


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


async def require_csrf(
    request: Request,
    settings: SettingsDep,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    """Enforce double-submit CSRF protection for cookie-authenticated requests.

    CSRF is required when the browser automatically attaches the session cookie.
    Requests authenticated via bearer tokens or API keys skip this guard.
    """

    if request.method.upper() in _SAFE_METHODS:
        return

    if principal.auth_via in {AuthVia.API_KEY, AuthVia.BEARER, AuthVia.DEV}:
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
