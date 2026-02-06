"""Database-only settings for migrations and DB tooling."""

from __future__ import annotations

from pydantic_settings import BaseSettings

from settings import (
    DatabaseSettingsMixin,
    DatabaseSettingsProtocol,
    ade_settings_config,
    create_settings_accessors,
)

DatabaseSettings = DatabaseSettingsProtocol


class Settings(DatabaseSettingsMixin, BaseSettings):
    """Settings required for database engine and migrations."""

    model_config = ade_settings_config()


get_settings, reload_settings = create_settings_accessors(Settings)


__all__ = ["DatabaseSettings", "Settings", "get_settings", "reload_settings"]
