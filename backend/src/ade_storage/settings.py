"""Storage settings and structural typing helpers."""

from __future__ import annotations

from pydantic_settings import BaseSettings

from settings import (
    BlobStorageSettingsMixin,
    BlobStorageSettingsProtocol,
    StorageLayoutSettingsProtocol,
    ade_settings_config,
    create_settings_accessors,
)

BlobStorageSettings = BlobStorageSettingsProtocol
StorageLayoutSettings = StorageLayoutSettingsProtocol


class Settings(BlobStorageSettingsMixin, BaseSettings):
    """Shared storage configuration loaded from ADE_* env vars."""

    model_config = ade_settings_config()


StorageSettings = Settings
get_settings, reload_settings = create_settings_accessors(Settings)


__all__ = [
    "BlobStorageSettings",
    "StorageLayoutSettings",
    "Settings",
    "StorageSettings",
    "get_settings",
    "reload_settings",
]
