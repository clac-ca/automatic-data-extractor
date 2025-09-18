"""Application configuration settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    """Runtime configuration for the ADE backend."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADE_", extra="ignore")

    database_url: str = Field(default="sqlite:///var/ade.sqlite", description="SQLAlchemy database URL")
    documents_dir: Path = Field(default=Path("var/documents"), description="Directory for uploaded documents")
    max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        description="Maximum accepted upload size for POST /documents",
    )

    @property
    def database_path(self) -> Path | None:
        """Return the filesystem path of the SQLite database if available."""

        url = make_url(self.database_url)
        if url.get_backend_name() != "sqlite":
            return None

        database = (url.database or "").strip()
        if not database or database == ":memory:":
            return None

        return Path(database)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


def reset_settings_cache() -> None:
    """Clear cached settings so future calls re-read the environment."""

    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
