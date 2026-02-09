"""Service factories used by API routers.

This module replaces the legacy ``shared.dependency`` helpers and should be
the single place routers import per-request service constructors from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ade_api.db import get_db_read, get_db_write
from ade_api.settings import Settings, get_settings
from ade_storage import StorageAdapter, get_storage_adapter

if TYPE_CHECKING:
    from ade_api.features.admin_settings.service import RuntimeSettingsService
    from ade_api.features.api_keys.service import ApiKeyService
    from ade_api.features.auth.service import AuthService
    from ade_api.features.configs.service import ConfigurationsService
    from ade_api.features.configs.storage import ConfigStorage
    from ade_api.features.documents.service import DocumentsService
    from ade_api.features.health.service import HealthService
    from ade_api.features.runs.service import RunsService
    from ade_api.features.sso.service import SsoService
    from ade_api.features.users.service import UsersService
    from ade_api.features.workspaces.service import WorkspacesService

WriteSessionDep = Annotated[Session, Depends(get_db_write)]
ReadSessionDep = Annotated[Session, Depends(get_db_read)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_blob_storage(request: Request) -> StorageAdapter:
    return get_storage_adapter(request)


StorageDep = Annotated[StorageAdapter, Depends(get_blob_storage)]


def _build_config_storage(settings: Settings) -> ConfigStorage:
    from ade_api.features.configs.storage import ConfigStorage

    return ConfigStorage(settings=settings)


def get_users_service(session: WriteSessionDep, settings: SettingsDep) -> UsersService:
    from ade_api.features.users.service import UsersService

    return UsersService(session=session, settings=settings)


def get_users_service_read(session: ReadSessionDep, settings: SettingsDep) -> UsersService:
    from ade_api.features.users.service import UsersService

    return UsersService(session=session, settings=settings)


def get_api_keys_service(session: WriteSessionDep, settings: SettingsDep) -> ApiKeyService:
    from ade_api.features.api_keys.service import ApiKeyService

    return ApiKeyService(session=session, settings=settings)


def get_api_keys_service_read(session: ReadSessionDep, settings: SettingsDep) -> ApiKeyService:
    from ade_api.features.api_keys.service import ApiKeyService

    return ApiKeyService(session=session, settings=settings)


def get_auth_service(session: WriteSessionDep, settings: SettingsDep) -> AuthService:
    from ade_api.features.auth.service import AuthService

    return AuthService(session=session, settings=settings)


def get_auth_service_read(session: ReadSessionDep, settings: SettingsDep) -> AuthService:
    from ade_api.features.auth.service import AuthService

    return AuthService(session=session, settings=settings)


def get_runtime_settings_service(session: WriteSessionDep) -> RuntimeSettingsService:
    from ade_api.features.admin_settings.service import RuntimeSettingsService

    return RuntimeSettingsService(session=session)


def get_runtime_settings_service_read(session: ReadSessionDep) -> RuntimeSettingsService:
    from ade_api.features.admin_settings.service import RuntimeSettingsService

    return RuntimeSettingsService(session=session)


def get_documents_service(
    session: WriteSessionDep, settings: SettingsDep, storage: StorageDep
) -> DocumentsService:
    from ade_api.features.documents.service import DocumentsService

    return DocumentsService(session=session, settings=settings, storage=storage)


def get_documents_service_read(
    session: ReadSessionDep, settings: SettingsDep, storage: StorageDep
) -> DocumentsService:
    from ade_api.features.documents.service import DocumentsService

    return DocumentsService(session=session, settings=settings, storage=storage)


def get_health_service(session: WriteSessionDep, settings: SettingsDep) -> HealthService:
    from ade_api.features.admin_settings.service import RuntimeSettingsService
    from ade_api.features.health.service import HealthService

    runtime_settings = RuntimeSettingsService(session=session)
    return HealthService(settings=settings, runtime_settings_service=runtime_settings)


def get_health_service_read(session: ReadSessionDep, settings: SettingsDep) -> HealthService:
    from ade_api.features.admin_settings.service import RuntimeSettingsService
    from ade_api.features.health.service import HealthService

    runtime_settings = RuntimeSettingsService(session=session)
    return HealthService(settings=settings, runtime_settings_service=runtime_settings)


def get_configurations_service(
    session: WriteSessionDep, settings: SettingsDep
) -> ConfigurationsService:
    from ade_api.features.configs.service import ConfigurationsService

    storage = _build_config_storage(settings)
    return ConfigurationsService(session=session, storage=storage)


def get_configurations_service_read(
    session: ReadSessionDep, settings: SettingsDep
) -> ConfigurationsService:
    from ade_api.features.configs.service import ConfigurationsService

    storage = _build_config_storage(settings)
    return ConfigurationsService(session=session, storage=storage)


def get_runs_service(
    session: WriteSessionDep, settings: SettingsDep, storage: StorageDep
) -> RunsService:
    from ade_api.features.runs.service import RunsService

    config_storage = _build_config_storage(settings)
    return RunsService(
        session=session,
        settings=settings,
        storage=config_storage,
        blob_storage=storage,
    )


def get_runs_service_read(
    session: ReadSessionDep, settings: SettingsDep, storage: StorageDep
) -> RunsService:
    from ade_api.features.runs.service import RunsService

    config_storage = _build_config_storage(settings)
    return RunsService(
        session=session,
        settings=settings,
        storage=config_storage,
        blob_storage=storage,
    )


def get_workspaces_service(
    session: WriteSessionDep, settings: SettingsDep
) -> WorkspacesService:
    from ade_api.features.workspaces.service import WorkspacesService

    return WorkspacesService(session=session, settings=settings)


def get_workspaces_service_read(
    session: ReadSessionDep, settings: SettingsDep
) -> WorkspacesService:
    from ade_api.features.workspaces.service import WorkspacesService

    return WorkspacesService(session=session, settings=settings)


def get_sso_service(session: WriteSessionDep, settings: SettingsDep) -> SsoService:
    from ade_api.features.sso.service import SsoService

    return SsoService(session=session, settings=settings)


def get_sso_service_read(session: ReadSessionDep, settings: SettingsDep) -> SsoService:
    from ade_api.features.sso.service import SsoService

    return SsoService(session=session, settings=settings)


__all__ = [
    "get_users_service",
    "get_users_service_read",
    "get_api_keys_service",
    "get_api_keys_service_read",
    "get_auth_service",
    "get_auth_service_read",
    "get_runtime_settings_service",
    "get_runtime_settings_service_read",
    "get_documents_service",
    "get_documents_service_read",
    "get_health_service",
    "get_health_service_read",
    "get_configurations_service",
    "get_configurations_service_read",
    "get_runs_service",
    "get_runs_service_read",
    "get_workspaces_service",
    "get_workspaces_service_read",
    "get_sso_service",
    "get_sso_service_read",
]
