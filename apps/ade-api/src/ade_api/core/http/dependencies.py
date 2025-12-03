"""FastAPI dependencies that bridge HTTP requests to the auth/RBAC foundation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.models.user import User
from ade_api.infra.db.session import get_session as get_db_session
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


class _NoopApiKeyAuthenticator:
    async def authenticate(self, _raw_token: str) -> AuthenticatedPrincipal | None:
        return None


class _NoopSessionAuthenticator:
    async def authenticate(self, _request: Request) -> AuthenticatedPrincipal | None:
        return None


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

    try:
        from ade_api.features.api_keys.service import ApiKeyService

        return ApiKeyService(session=db, settings=settings)
    except Exception:
        return _NoopApiKeyAuthenticator()


def get_session_authenticator(
    db: SessionDep,
    settings: SettingsDep,
) -> SessionAuthenticator:
    """Authenticate bearer tokens issued by the auth feature."""

    try:
        from ade_api.features.auth.service import AuthService
    except Exception:
        return _NoopSessionAuthenticator()

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
):
    """Return a dependency enforcing a specific permission."""

    async def dependency(
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
        db: SessionDep,
        rbac: Annotated[RbacServiceInterface, Depends(get_rbac_service)],
    ) -> AuthenticatedPrincipal:
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


def require_global(permission_key: str):
    return require_permission(permission_key, workspace_param=None)


def require_workspace(permission_key: str, workspace_param: str = "workspace_id"):
    return require_permission(permission_key, workspace_param=workspace_param)


async def require_csrf() -> None:
    """No-op CSRF guard placeholder (to be implemented with session auth)."""

    return None
