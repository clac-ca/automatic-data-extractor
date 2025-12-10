"""Settings for ade_engine using pydantic-settings.

Defines a minimal set of engine-level toggles loaded from (in precedence order):
init kwargs > env vars > .env file > settings.toml > defaults.
"""
from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _toml_settings_source() -> dict[str, Any]:
    """Load settings from ``settings.toml`` if present.

    The function returns a flat dict suitable for pydantic-settings.  We accept
    either top-level keys or a nested ``[ade_engine]`` table for flexibility.
    """

    path = Path("settings.toml")
    if not path.exists():
        return {}

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    # Prefer nested table to avoid collisions with other tooling.
    nested = data.get("ade_engine")
    if isinstance(nested, dict):
        return nested
    return data


class Settings(BaseSettings):
    """Runtime settings for the engine.

    Defaults are safe for local development.  Callers can override via init
    kwargs, environment variables (``ADE_ENGINE_*``), a ``.env`` file, or an
    optional ``settings.toml``.
    """

    model_config = SettingsConfigDict(
        env_prefix="ADE_ENGINE_",
        env_file=".env",
        extra="ignore",
    )

    # Core paths / packages
    config_package: str | None = Field(
        default=None,
        description="(Required) Path to the config package directory (contains ade_config).",
    )

    # Output / writer toggles
    append_unmapped_columns: bool = Field(
        default=True,
        description="Whether to include unmapped source columns in the output workbook.",
    )
    unmapped_prefix: str = Field(
        default="raw_",
        description="Prefix applied to unmapped column headers when appended to output.",
    )

    # Mapping behavior
    mapping_tie_resolution: Literal["leftmost", "leave_unmapped"] = Field(
        default="leftmost",
        description=(
            "How to resolve multiple source columns mapping to the same field: "
            "'leftmost' keeps the earliest column, 'leave_unmapped' leaves all unmapped."
        ),
    )

    # Logging
    log_format: Literal["text", "ndjson"] = Field(default="text")
    log_level: int = Field(default=logging.INFO)

    # Scan limits
    max_empty_rows_run: int | None = Field(
        default=1000,
        description="Stop scanning a sheet after this many consecutive empty rows. None disables the guard.",
        ge=1,
    )
    max_empty_cols_run: int | None = Field(
        default=500,
        description=(
            "When reading a row, stop after this many consecutive empty cells once past the last non-empty "
            "cell seen. Helps avoid huge trailing empty columns. None disables the guard."
        ),
        ge=1,
    )

    # File discovery
    supported_file_extensions: tuple[str, ...] = Field(
        default=(".xlsx", ".xlsm", ".csv"),
        description="File extensions considered when scanning directories for inputs (case-insensitive).",
    )

    @field_validator("unmapped_prefix")
    @classmethod
    def _ensure_prefix_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("unmapped_prefix must be non-empty")
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):  # type: ignore[override]
        toml_source = lambda: _toml_settings_source()
        # Precedence: init > env vars > .env > TOML > defaults
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            toml_source,
            file_secret_settings,
        )


__all__ = ["Settings"]
