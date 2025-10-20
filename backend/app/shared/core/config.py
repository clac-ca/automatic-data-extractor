from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Automatic Data Extractor API"
    app_version: str = "0.1.0"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    api_v1_prefix: str = "/api/v1"

    cors_allow_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = True

    static_mount_path: str = "/"
    static_directory: str = "backend/app/web/static"

    environment: str = Field(default="local", validation_alias="ENVIRONMENT")

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="allow",
    )

    @computed_field(return_type=Path)
    def static_dir(self) -> Path:
        return Path(self.static_directory).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
