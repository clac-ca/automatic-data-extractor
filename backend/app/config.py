"""Application configuration settings."""

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

    @property
    def database_path(self) -> Path:
        """Return the filesystem path of the SQLite database."""

        url = make_url(self.database_url)
        if url.get_backend_name() != "sqlite":
            msg = "database_path is only defined for SQLite URLs"
            raise ValueError(msg)
        if not url.database:
            msg = "SQLite URL must include a database path"
            raise ValueError(msg)
        return Path(url.database)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


__all__ = ["Settings", "get_settings"]
