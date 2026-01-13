"""Service factories used by API routers.

This module replaces the legacy ``shared.dependency`` helpers and should be
the single place routers import per-request service constructors from.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from ade_api.db import get_db
from ade_api.settings import Settings, get_settings

SessionDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


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


def get_runs_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.runs.service import RunsService

    storage = _build_config_storage(settings)
    return RunsService(session=session, settings=settings, storage=storage)


def get_workspaces_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.workspaces.service import WorkspacesService

    return WorkspacesService(session=session, settings=settings)


def get_idempotency_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.idempotency.service import IdempotencyService

    return IdempotencyService(session=session, settings=settings)


def get_sso_service(session: SessionDep, settings: SettingsDep):
    from ade_api.features.sso.service import SsoService

    return SsoService(session=session, settings=settings)


__all__ = [
    "get_users_service",
    "get_api_keys_service",
    "get_auth_service",
    "get_system_settings_service",
    "get_documents_service",
    "get_health_service",
    "get_safe_mode_service",
    "get_configurations_service",
    "get_runs_service",
    "get_workspaces_service",
    "get_idempotency_service",
    "get_sso_service",
]
