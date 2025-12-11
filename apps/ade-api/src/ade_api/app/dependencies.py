"""Service factories used by API routers.

This module replaces the legacy ``shared.dependency`` helpers and should be
the single place routers import per-request service constructors from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from fastapi import Path as PathParam
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.http import require_authenticated
from ade_api.core.http.dependencies import get_current_principal as _get_current_principal
from ade_api.infra.db.session import get_session
from ade_api.settings import Settings, get_settings

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
get_db_session = get_session
get_current_principal = _get_current_principal

if TYPE_CHECKING:
    from ade_api.features.runs.event_stream import RunEventStreamRegistry


def _build_config_storage(settings: Settings):
    from ade_api.features.configs.storage import ConfigStorage

    if settings.configs_dir is None:
        raise RuntimeError("ADE_CONFIGS_DIR is not configured")
    return ConfigStorage(settings=settings)


def get_users_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.users.service import UsersService

    return UsersService(session=session, settings=settings)


def get_api_keys_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.api_keys.service import ApiKeyService

    return ApiKeyService(session=session, settings=settings)


def get_auth_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.auth.service import AuthService

    return AuthService(session=session, settings=settings)


def get_system_settings_service(session: SessionDep):
    from ade_api.features.system_settings.service import SystemSettingsService

    return SystemSettingsService(session=session)


def get_documents_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.documents.service import DocumentsService

    return DocumentsService(session=session, settings=settings)


def get_health_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.health.service import HealthService
    from ade_api.features.system_settings.service import SafeModeService

    safe_mode = SafeModeService(session=session, settings=settings)
    return HealthService(settings=settings, safe_mode_service=safe_mode)


def get_safe_mode_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.system_settings.service import SafeModeService

    return SafeModeService(session=session, settings=settings)


def get_configurations_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.configs.service import ConfigurationsService

    storage = _build_config_storage(settings)
    return ConfigurationsService(session=session, storage=storage)


def get_builds_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.builds.service import BuildsService

    event_streams = get_run_event_streams()
    storage = _build_config_storage(settings)
    return BuildsService(
        session=session,
        settings=settings,
        storage=storage,
        event_streams=event_streams,
    )


def get_runs_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.runs.service import RunsService
    from ade_api.features.runs.supervisor import RunExecutionSupervisor
    from ade_api.features.system_settings.service import SafeModeService

    storage = _build_config_storage(settings)
    event_streams = get_run_event_streams()
    supervisor = RunExecutionSupervisor()

    return RunsService(
        session=session,
        settings=settings,
        supervisor=supervisor,
        safe_mode_service=SafeModeService(session=session, settings=settings),
        storage=storage,
        event_streams=event_streams,
        build_event_streams=event_streams,
    )


def get_workspaces_service(session: SessionDep):
    from ade_api.features.workspaces.service import WorkspacesService

    return WorkspacesService(session=session)


_RUN_EVENT_STREAMS: RunEventStreamRegistry | None = None


def get_run_event_streams() -> RunEventStreamRegistry:
    """Provide a process-wide RunEventStreamRegistry."""

    from ade_api.features.runs.event_stream import RunEventStreamRegistry

    global _RUN_EVENT_STREAMS
    if _RUN_EVENT_STREAMS is None:
        _RUN_EVENT_STREAMS = RunEventStreamRegistry()
    return _RUN_EVENT_STREAMS


async def get_workspace_profile(
    current_user: Annotated[object, Depends(require_authenticated)],
    session: SessionDep,
    workspace_id: Annotated[
        str,
        PathParam(
            min_length=1,
            description="Workspace identifier",
        ),
    ],
) -> object:
    from ade_api.features.workspaces.service import WorkspacesService

    service = WorkspacesService(session=session)
    return await service.get_workspace_profile(user=current_user, workspace_id=workspace_id)


__all__ = [
    "get_current_principal",
    "get_db_session",
    "get_users_service",
    "get_api_keys_service",
    "get_auth_service",
    "get_system_settings_service",
    "get_documents_service",
    "get_health_service",
    "get_safe_mode_service",
    "get_configurations_service",
    "get_builds_service",
    "get_runs_service",
    "get_workspaces_service",
    "get_run_event_streams",
    "get_workspace_profile",
]
