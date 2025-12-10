"""Minimal engine settings (external to the manifest)."""

from __future__ import annotations

import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_PACKAGE = "ade_config"
DEFAULT_SUPPORTED_FILE_EXTENSIONS: tuple[str, ...] = (".xlsx", ".csv")
DEFAULT_LOG_FORMAT = "text"


class Settings(BaseSettings):
    """
    External defaults; pipeline behavior comes from the config manifest.

    Pydantic-driven parsing gives us:
    - env var overrides (prefix: ADE_ENGINE_)
    - immutability (frozen) so settings stay consistent across the run
    """

    model_config = SettingsConfigDict(
        env_prefix="ADE_ENGINE_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    config_package: str = DEFAULT_CONFIG_PACKAGE
    supported_file_extensions: tuple[str, ...] = DEFAULT_SUPPORTED_FILE_EXTENSIONS
    log_level: int = logging.INFO
    log_format: str = DEFAULT_LOG_FORMAT

    @field_validator("log_format", mode="before")
    @classmethod
    def _normalize_log_format(cls, value: object) -> str:
        """Normalize log format; allow only text or ndjson."""
        fmt = DEFAULT_LOG_FORMAT if value is None else str(value).strip().lower()
        if fmt not in {"text", "ndjson"}:
            raise ValueError("log_format must be 'text' or 'ndjson'")
        return fmt

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> int:
        if value is None:
            return logging.INFO
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            mapping = logging.getLevelNamesMapping()
            resolved = mapping.get(value.upper())
            if isinstance(resolved, int):
                return resolved
        raise ValueError("log_level must be an int or a standard logging level name")


__all__ = ["Settings"]
