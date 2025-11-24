"""Shared dependency providers for API routes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path as FilePath
from typing import TYPE_CHECKING, Annotated

import jwt
from fastapi import Depends, HTTPException, Path, Request, Security, status
from fastapi.security import (
    APIKeyCookie,
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
    SecurityScopes,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.auth.service import AuthenticatedIdentity, AuthService
from ade_api.features.roles.authorization import authorize
from ade_api.features.roles.models import ScopeType
from ade_api.features.roles.service import ensure_user_principal
from ade_api.features.runs.supervisor import RunSupervisor
from ade_api.features.users.models import User
from ade_api.features.workspaces.schemas import WorkspaceOut
from ade_api.settings import Settings, get_settings
from ade_api.shared.core.security import (
    forbidden_response,
    resolve_workspace_scope,
)
from ade_api.shared.db.session import get_session

if TYPE_CHECKING:
    from ade_api.features.builds.service import BuildsService
    from ade_api.features.configs.service import ConfigurationsService
    from ade_api.features.documents.service import DocumentsService
    from ade_api.features.health.service import HealthService
    from ade_api.features.jobs.service import JobsService
    from ade_api.features.runs.service import RunsService
    from ade_api.features.system_settings.service import SafeModeService, SystemSettingsService
    from ade_api.features.users.service import UsersService


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_RUN_SUPERVISOR = RunSupervisor()


def get_users_service(session: SessionDep) -> UsersService:
    """Return a users service bound to the current database session."""

    from ade_api.features.users.service import UsersService

    return UsersService(session=session)


def get_system_settings_service(session: SessionDep) -> SystemSettingsService:
    """Return a request-scoped system settings service."""

    from ade_api.features.system_settings.service import SystemSettingsService

    return SystemSettingsService(session=session)


def get_documents_service(
    session: SessionDep,
    settings: SettingsDep,
) -> DocumentsService:
    """Construct a ``DocumentsService`` for request-scoped operations."""

    from ade_api.features.documents.service import DocumentsService

    return DocumentsService(session=session, settings=settings)


def get_health_service(
    session: SessionDep, settings: SettingsDep
) -> HealthService:
    """Return a health service configured for the current request."""

    from ade_api.features.health.service import HealthService
    from ade_api.features.system_settings.service import SafeModeService

    safe_mode = SafeModeService(session=session, settings=settings)
    return HealthService(settings=settings, safe_mode_service=safe_mode)


def get_safe_mode_service(
    session: SessionDep, settings: SettingsDep
) -> SafeModeService:
    """Return a safe mode service for toggling ADE runtime state."""

    from ade_api.features.system_settings.service import SafeModeService

    return SafeModeService(session=session, settings=settings)


def get_configs_service(
    session: SessionDep,
    settings: SettingsDep,
) -> ConfigurationsService:
    """Return a configurations service for workspace config APIs."""

    from ade_api.features.configs.service import ConfigurationsService
    from ade_api.features.configs.storage import ConfigStorage

    if settings.configs_dir is None:
        raise RuntimeError("ADE_CONFIGS_DIR is not configured")

    module_root = FilePath(__file__).resolve().parents[1]
    templates_root = module_root / "templates" / "config_packages"
    storage = ConfigStorage(
        templates_root=templates_root,
        configs_root=settings.configs_dir,
    )
    return ConfigurationsService(session=session, storage=storage)


def get_builds_service(
    session: SessionDep,
    settings: SettingsDep,
) -> BuildsService:
    """Return a builds service for virtual environment lifecycle APIs."""

    from ade_api.features.builds.service import BuildsService
    from ade_api.features.configs.storage import ConfigStorage

    if settings.configs_dir is None:
        raise RuntimeError("ADE_CONFIGS_DIR is not configured")

    module_root = FilePath(__file__).resolve().parents[1]
    templates_root = module_root / "templates" / "config_packages"
    storage = ConfigStorage(
        templates_root=templates_root,
        configs_root=settings.configs_dir,
    )
    return BuildsService(session=session, settings=settings, storage=storage)


def get_runs_service(
    session: SessionDep,
    settings: SettingsDep,
) -> RunsService:
    """Return a runs service wired to the current request dependencies."""

    from ade_api.features.runs.service import RunsService

    return RunsService(
        session=session,
        settings=settings,
        supervisor=_RUN_SUPERVISOR,
        safe_mode_service=get_safe_mode_service(session=session, settings=settings),
    )


def get_jobs_service(
    session: SessionDep,
    settings: SettingsDep,
) -> JobsService:
    """Return a jobs service configured for the current request."""

    from ade_api.features.jobs.service import JobsService

    return JobsService(session=session, settings=settings)


_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_session_cookie_scheme = APIKeyCookie(
    name="ade_session",
    scheme_name="SessionCookie",
    auto_error=False,
)

def _is_dev_identity(identity: AuthenticatedIdentity) -> bool:
    return identity.credentials == "development"


def configure_auth_dependencies(*, settings: Settings) -> None:
    """Configure authentication dependency state for the application lifecycle."""

    _session_cookie_scheme.model.name = settings.session_cookie_name


async def get_current_identity(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer_scheme)
    ],
    api_key: Annotated[str | None, Security(_api_key_scheme)],
    session_cookie: Annotated[str | None, Security(_session_cookie_scheme)],
    session: SessionDep,
    settings: SettingsDep,
) -> AuthenticatedIdentity:
    """Resolve the authenticated identity for the request."""

    service = AuthService(session=session, settings=settings)
    if settings.auth_disabled:
        return await service.ensure_dev_identity()

    if credentials is not None:
        try:
            payload = service.decode_token(
                credentials.credentials,
                expected_type="access",
            )
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc
        user = await service.resolve_user(payload)
        principal = await ensure_user_principal(session=session, user=user)
        return AuthenticatedIdentity(
            user=user,
            principal=principal,
            credentials="bearer_token",
        )

    raw_cookie = session_cookie or request.cookies.get(
        service.settings.session_cookie_name
    )
    cookie_value = (raw_cookie or "").strip()
    if cookie_value:
        try:
            payload = service.decode_token(cookie_value, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session",
            ) from exc
        service.enforce_csrf(request, payload)
        user = await service.resolve_user(payload)
        principal = await ensure_user_principal(session=session, user=user)
        return AuthenticatedIdentity(
            user=user,
            principal=principal,
            credentials="session_cookie",
        )

    if api_key:
        identity = await service.authenticate_api_key(api_key, request=request)
        return identity

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def get_current_user(
    principal: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> User:
    """Resolve the authenticated user principal."""

    return principal.user


async def require_authenticated(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Ensure the request is associated with an authenticated user."""

    return user


async def require_csrf(
    request: Request,
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    """Enforce CSRF validation for mutating requests."""

    if identity.credentials != "session_cookie":
        return

    service = AuthService(session=session, settings=settings)
    access_payload, _ = service.extract_session_payloads(
        request,
        include_refresh=False,
    )
    service.enforce_csrf(request, access_payload)


def require_global(
    permission: str,
) -> Callable[[SecurityScopes, AuthenticatedIdentity, AsyncSession], User]:
    """Return a dependency that enforces a global permission."""

    async def dependency(
        _security_scopes: SecurityScopes,
        identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
        session: SessionDep,
    ) -> User:
        if _is_dev_identity(identity):
            return identity.user
        decision = await authorize(
            session=session,
            principal_id=str(identity.principal.id),
            permission_key=permission,
            scope_type=ScopeType.GLOBAL,
        )
        if not decision.is_authorized:
            raise forbidden_response(
                permission=permission,
                scope_type=ScopeType.GLOBAL,
                scope_id=None,
            )
        return identity.user

    return dependency


def require_workspace(
    permission: str,
    *,
    scope_param: str = "workspace_id",
) -> Callable[[Request, SecurityScopes, AuthenticatedIdentity, AsyncSession], User]:
    """Return a dependency that enforces a workspace-scoped permission."""

    async def dependency(
        request: Request,
        security_scopes: SecurityScopes,
        identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
        session: SessionDep,
    ) -> User:
        if _is_dev_identity(identity):
            return identity.user
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
            scope_type=ScopeType.WORKSPACE,
            scope_id=workspace_id,
        )
        if not decision.is_authorized:
            raise forbidden_response(
                permission=permission,
                scope_type=ScopeType.WORKSPACE,
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
    [Request, SecurityScopes, str, str | None, AuthenticatedIdentity, AsyncSession],
    User,
]:
    """Return a dependency that validates permission catalog access by scope."""

    async def dependency(
        request: Request,
        security_scopes: SecurityScopes,
        scope: str,
        identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
        session: SessionDep,
        workspace_id: str | None = None,
    ) -> User:
        if _is_dev_identity(identity):
            return identity.user
        if scope == ScopeType.GLOBAL:
            decision = await authorize(
                session=session,
                principal_id=str(identity.principal.id),
                permission_key=global_permission,
                scope_type=ScopeType.GLOBAL,
            )
            if not decision.is_authorized:
                raise forbidden_response(
                    permission=global_permission,
                    scope_type=ScopeType.GLOBAL,
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
            scope_type=ScopeType.WORKSPACE,
            scope_id=candidate,
        )
        if not decision.is_authorized:
            raise forbidden_response(
                permission=workspace_permission,
                scope_type=ScopeType.WORKSPACE,
                scope_id=candidate,
            )
        return identity.user

    return dependency


async def get_workspace_profile(
    current_user: Annotated[User, Security(require_authenticated)],
    session: SessionDep,
    workspace_id: Annotated[
        str,
        Path(
            min_length=1,
            description="Workspace identifier",
        ),
    ],
) -> WorkspaceOut:
    """Return the active workspace membership profile for the request."""

    normalized = workspace_id.strip()
    if not normalized:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Workspace identifier required",
        )

    from ade_api.features.workspaces.service import WorkspacesService

    service = WorkspacesService(session=session)
    return await service.get_workspace_profile(
        user=current_user,
        workspace_id=normalized,
    )


__all__ = [
    "SessionDep",
    "SettingsDep",
    "configure_auth_dependencies",
    "get_current_identity",
    "get_current_user",
    "get_configs_service",
    "get_documents_service",
    "get_health_service",
    "get_runs_service",
    "get_safe_mode_service",
    "get_system_settings_service",
    "get_users_service",
    "get_workspace_profile",
    "require_authenticated",
    "require_csrf",
    "require_global",
    "require_permissions_catalog_access",
    "require_workspace",
]
