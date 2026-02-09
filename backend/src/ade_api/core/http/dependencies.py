"""FastAPI dependencies that bridge HTTP requests to the auth/RBAC foundation."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from ade_api.common.time import utc_now
from ade_api.db import get_db_read, get_session_factory
from ade_api.settings import Settings, get_settings
from ade_db.models import AUTH_SESSION_AUTH_METHOD_VALUES, ApiKey, AuthSession, User

from ..auth import (
    AuthenticatedPrincipal,
    AuthenticationError,
    PermissionDeniedError,
    authenticate_request,
)
from ..auth.pipeline import ApiKeyAuthenticator, CookieAuthenticator
from ..auth.principal import AuthVia, PrincipalType
from ..rbac.service_interface import RbacService as RbacServiceInterface
from ..security.tokens import hash_opaque_token

ReadSessionDep = Annotated[Session, Depends(get_db_read)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

PermissionDependency = Callable[..., User]
_KNOWN_AUTH_METHODS = set(AUTH_SESSION_AUTH_METHOD_VALUES)
_MFA_SETUP_ALLOWLIST = {
    "/api/v1/auth/logout",
    "/api/v1/auth/password/change",
    "/api/v1/me/bootstrap",
}
_PASSWORD_CHANGE_ALLOWLIST = {
    "/api/v1/auth/logout",
    "/api/v1/auth/password/change",
    "/api/v1/me/bootstrap",
}

class _RbacAdapter(RbacServiceInterface):
    """Bridge the RBAC feature service to the interface expected by dependencies."""

    def __init__(self, *, session: Session):
        super().__init__(session=session)

        from ade_api.features.rbac.service import RbacService

        self._service = RbacService(session=session)

    def _resolve_user(self, principal: AuthenticatedPrincipal) -> User:
        user = self.session.get(User, principal.user_id)
        if user is None:
            raise AuthenticationError("Unknown principal")
        if not getattr(user, "is_active", True):
            raise AuthenticationError("User account is inactive.")
        return user

    def sync_registry(self) -> None:
        self._service.sync_registry()

    def get_global_role_slugs(
        self,
        principal: AuthenticatedPrincipal,
    ) -> set[str]:
        user = self._resolve_user(principal)
        result = self._service.get_global_role_slugs_for_user(user=user)
        return set(result)

    def get_global_permissions(
        self,
        principal: AuthenticatedPrincipal,
    ) -> set[str]:
        user = self._resolve_user(principal)
        result = self._service.get_global_permissions_for_user(user=user)
        return set(result)

    def get_workspace_permissions(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID | None = None,
    ) -> set[str]:
        if workspace_id is None:
            return set()

        user = self._resolve_user(principal)
        result = self._service.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_id,
        )
        return set(result)

    def get_effective_permissions(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID | None = None,
    ) -> set[str]:
        global_permissions = self.get_global_permissions(principal=principal)
        if workspace_id is None:
            return global_permissions

        workspace_permissions = self.get_workspace_permissions(
            principal=principal,
            workspace_id=workspace_id,
        )
        return global_permissions.union(workspace_permissions)

    def has_permission(
        self,
        principal: AuthenticatedPrincipal,
        permission_key: str,
        workspace_id: UUID | None = None,
    ) -> bool:
        from ade_api.features.rbac.service import AuthorizationError

        try:
            user = self._resolve_user(principal)
            decision = self._service.authorize(
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
    db: ReadSessionDep,
    settings: SettingsDep,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> ApiKeyAuthenticator:
    """Provide the API key authenticator."""

    from ade_api.features.api_keys.service import (
        ApiKeyExpiredError,
        ApiKeyNotFoundError,
        ApiKeyOwnerInactiveError,
        ApiKeyRevokedError,
        ApiKeyService,
        InvalidApiKeyFormatError,
    )

    service = ApiKeyService(session=db, settings=settings)

    class _ApiKeyAuthenticator:
        def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
            self._session_factory = session_factory

        def _touch_usage(self, api_key_id: UUID) -> None:
            with self._session_factory() as session:
                session.execute(
                    update(ApiKey)
                    .where(ApiKey.id == api_key_id)
                    .values(last_used_at=utc_now())
                )
                session.commit()

        def authenticate(self, raw_token: str) -> AuthenticatedPrincipal | None:
            try:
                result = service.authenticate_token(raw_token, touch_usage=False)
            except (
                InvalidApiKeyFormatError,
                ApiKeyNotFoundError,
                ApiKeyExpiredError,
                ApiKeyRevokedError,
                ApiKeyOwnerInactiveError,
            ) as exc:
                raise AuthenticationError(str(exc)) from exc

            api_key = result.api_key
            principal = AuthenticatedPrincipal(
                user_id=result.user_id,
                principal_type=PrincipalType.USER,
                auth_via=AuthVia.API_KEY,
                api_key_id=api_key.id,
            )
            self._touch_usage(api_key.id)
            return principal

    return _ApiKeyAuthenticator(session_factory=session_factory)


def get_api_key_authenticator_websocket(
    db: Session,
    settings: SettingsDep,
) -> ApiKeyAuthenticator:
    """Provide the API key authenticator for WebSocket endpoints."""

    from ade_api.features.api_keys.service import ApiKeyService

    return ApiKeyService(session=db, settings=settings)


def get_cookie_authenticator(
    db: ReadSessionDep,
    settings: SettingsDep,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> CookieAuthenticator:
    """Authenticate cookie session tokens against the auth_sessions table."""

    class _CookieAuthenticator:
        def _expire_token(self, session_id: UUID) -> None:
            with session_factory() as session:
                session.execute(
                    update(AuthSession)
                    .where(AuthSession.id == session_id)
                    .where(AuthSession.revoked_at.is_(None))
                    .values(revoked_at=utc_now())
                )
                session.commit()

        def authenticate(self, token: str) -> AuthenticatedPrincipal | None:
            candidate = (token or "").strip()
            if not candidate:
                return None

            token_hash = hash_opaque_token(candidate)
            stmt = (
                select(AuthSession)
                .where(AuthSession.token_hash == token_hash)
                .where(AuthSession.revoked_at.is_(None))
                .limit(1)
            )
            result = db.execute(stmt)
            auth_session = result.scalar_one_or_none()
            if auth_session is None:
                return None

            now = utc_now()
            expires_at = auth_session.expires_at
            if expires_at is not None and expires_at <= now:
                self._expire_token(auth_session.id)
                return None

            user = db.get(User, auth_session.user_id)
            if user is None:
                return None

            return AuthenticatedPrincipal(
                user_id=user.id,
                principal_type=PrincipalType.USER,
                auth_via=AuthVia.SESSION,
                api_key_id=None,
                session_auth_method=_normalize_session_auth_method(
                    auth_session.auth_method
                ),
            )

    return _CookieAuthenticator()


def get_rbac_service(
    db: ReadSessionDep,
) -> RbacServiceInterface:
    """Return the RBAC service implementation."""

    return _RbacAdapter(session=db)


def get_current_principal(
    request: Request,
    db: ReadSessionDep,
    settings: SettingsDep,
    api_key_service: Annotated[
        ApiKeyAuthenticator,
        Depends(get_api_key_authenticator),
    ],
    cookie_service: Annotated[
        CookieAuthenticator,
        Depends(get_cookie_authenticator),
    ],
) -> AuthenticatedPrincipal:
    """Authenticate the incoming request and return the current principal."""

    principal = authenticate_request(
        request=request,
        _db=db,
        settings=settings,
        api_key_service=api_key_service,
        cookie_service=cookie_service,
    )
    _enforce_password_mfa_onboarding(
        request=request,
        db=db,
        settings=settings,
        principal=principal,
    )
    _enforce_password_change_requirement(
        request=request,
        db=db,
        principal=principal,
    )
    return principal


def _normalize_session_auth_method(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in _KNOWN_AUTH_METHODS else "unknown"


def _is_mfa_allowlisted_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in _MFA_SETUP_ALLOWLIST:
        return True
    if normalized.startswith("/api/v1/auth/mfa/totp"):
        return True
    return False


def _is_password_change_allowlisted_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in _PASSWORD_CHANGE_ALLOWLIST:
        return True
    if normalized.startswith("/api/v1/auth/mfa/totp"):
        return True
    return False


def _enforce_password_mfa_onboarding(
    *,
    request: Request,
    db: Session,
    settings: Settings,
    principal: AuthenticatedPrincipal,
) -> None:
    if principal.auth_via is not AuthVia.SESSION:
        return
    if principal.session_auth_method != "password":
        return
    if _is_mfa_allowlisted_path(request.url.path):
        return

    from ade_api.features.authn.service import AuthnService

    authn = AuthnService(session=db, settings=settings)
    if not authn.get_policy().password_mfa_required:
        return
    if authn.has_mfa_enabled(user_id=principal.user_id):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "mfa_setup_required",
            "message": (
                "Multi-factor authentication setup is required before continuing."
            ),
        },
    )


def _enforce_password_change_requirement(
    *,
    request: Request,
    db: Session,
    principal: AuthenticatedPrincipal,
) -> None:
    if principal.auth_via is not AuthVia.SESSION:
        return
    if principal.session_auth_method != "password":
        return
    if _is_password_change_allowlisted_path(request.url.path):
        return

    user = db.get(User, principal.user_id)
    if user is None:
        return
    if not bool(user.must_change_password):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "password_change_required",
            "message": "You must change your password before continuing.",
        },
    )


def require_authenticated(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    db: ReadSessionDep,
) -> User:
    """Ensure the request is authenticated and return the persisted user."""

    user = db.get(User, principal.user_id)
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

    def dependency(
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
        db: ReadSessionDep,
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
        allowed = rbac.has_permission(
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
        user = db.get(User, principal.user_id)
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


def require_csrf(
    request: Request,
    settings: SettingsDep,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    """Enforce double-submit CSRF protection for cookie-authenticated requests.

    CSRF is required when the browser automatically attaches the session cookie.
    Requests authenticated via API keys skip this guard.
    """

    if request.method.upper() in _SAFE_METHODS:
        return

    if principal.auth_via in {AuthVia.API_KEY, AuthVia.DEV}:
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
