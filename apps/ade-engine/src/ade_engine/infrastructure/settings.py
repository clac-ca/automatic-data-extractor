"""Settings for :mod:`ade_engine` (infrastructure).

Settings are defined in one place (this file) and loaded using `pydantic-settings`.

Supported sources (lowest → highest precedence):
1) `settings.toml` (current working directory)
2) `settings.toml` (config package directory; when provided)
3) `.env` (current working directory)
4) environment variables (prefix: `ADE_ENGINE_`)
5) explicit overrides (`Settings(...)` / CLI)

`settings.toml` is intentionally flat: keys map 1:1 to `Settings` fields.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseSettingsSource, TomlConfigSettingsSource

ENV_PREFIX = "ADE_ENGINE_"


def _coerce_log_level(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("log_level must be an int or a log level name")

    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return logging.INFO

    if text.isdigit():
        return int(text)

    mapped = logging.getLevelNamesMapping().get(text.upper())
    if isinstance(mapped, int):
        return mapped

    raise ValueError(f"Invalid log_level: {value!r}")


def _coerce_supported_file_extensions(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return tuple(items)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ()
        if "," in text:
            return tuple(part.strip() for part in text.split(",") if part.strip())
        return (text,)

    raise TypeError("supported_file_extensions must be a list/tuple of strings or a comma-separated string")


class Settings(BaseSettings):
    """Runtime settings for the engine."""

    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix=ENV_PREFIX,
        env_file=".env",
    )

    # Optional default config package resolution (used by CLI when --config-package is omitted).
    config_package: Path | None = Field(
        default=None,
        description="Path to the config package directory (contains ade_config).",
    )

    # Output / writer policy
    remove_unmapped_columns: bool = Field(default=False)
    write_diagnostics_columns: bool = Field(default=False)

    # Mapping behavior
    mapping_tie_resolution: Literal["leftmost", "leave_unmapped"] = Field(default="leftmost")

    # Logging
    log_format: Literal["text", "ndjson"] = Field(default="text")
    log_level: int = Field(default=logging.INFO)

    # Scan limits
    max_empty_rows_run: int | None = Field(default=1000, ge=1)
    max_empty_cols_run: int | None = Field(default=500, ge=1)

    # Detector sampling policy (detection stage only)
    detector_column_sample_size: int = Field(default=100, ge=1)

    # File discovery
    supported_file_extensions: tuple[str, ...] = Field(default=(".xlsx", ".xlsm", ".csv"))

    @field_validator("log_level", mode="before")
    @classmethod
    def _validate_log_level(cls, value: Any) -> int:
        return _coerce_log_level(value)

    @field_validator("supported_file_extensions", mode="before")
    @classmethod
    def _validate_supported_file_extensions(cls, value: Any) -> tuple[str, ...]:
        coerced = _coerce_supported_file_extensions(value)
        if not coerced:
            return coerced

        normalized: list[str] = []
        for ext in coerced:
            ext = ext.strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext.lstrip('*.')}"
            normalized.append(ext)
        return tuple(normalized)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_files = None
        if hasattr(init_settings, "init_kwargs"):
            toml_files = init_settings.init_kwargs.get("_ade_toml_files")  # type: ignore[attr-defined]

        if toml_files is None:
            toml_files = [Path.cwd() / "settings.toml"]

        toml_settings = TomlConfigSettingsSource(settings_cls, toml_file=toml_files)

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            toml_settings,
            file_secret_settings,
        )

    @classmethod
    def load(
        cls,
        *,
        config_package_dir: Path | None = None,
        cwd: Path | None = None,
        **overrides: Any,
    ) -> "Settings":
        cwd_path = (cwd or Path.cwd()).expanduser().resolve()

        toml_files: list[Path] = [cwd_path / "settings.toml"]
        if config_package_dir is not None:
            cfg_path = Path(config_package_dir).expanduser().resolve()
            toml_files.append(cfg_path / "settings.toml")
            overrides.setdefault("config_package", cfg_path)

        return cls(
            _ade_toml_files=toml_files,
            _env_file=cwd_path / ".env",
            **overrides,
        )


__all__ = ["ENV_PREFIX", "Settings"]
