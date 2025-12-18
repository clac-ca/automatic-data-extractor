"""Settings for ade_engine (infrastructure).

The engine loads settings from (lowest → highest precedence):
1) ``settings.toml`` in the current working directory
2) ``settings.toml`` in the config package directory (if available)
3) ``.env`` (current working directory)
4) environment variables (prefix: ``ADE_ENGINE_``)
5) explicit overrides (kwargs / CLI)

The TOML file may use either top-level keys or a nested ``[ade_engine]`` table.
"""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator

from ade_engine.models.detectors import DetectorSettings

ENV_PREFIX = "ADE_ENGINE_"


def _load_settings_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(raw, dict):
        return {}

    nested = raw.get("ade_engine")
    if isinstance(nested, dict):
        # Merge [ade_engine] into the top-level map so nested tables (e.g. [ade_engine.detectors])
        # remain visible to the settings model.
        combined = dict(raw)
        combined.pop("ade_engine", None)
        combined.update(nested)
        return combined

    return raw


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
            value = value[1:-1]

        env[key] = value

    return env


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


class Settings(BaseModel):
    """Runtime settings for the engine."""

    # Optional default config package resolution (used by CLI when --config-package is omitted).
    config_package: str | None = Field(
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

    # Detector sampling policy
    detectors: DetectorSettings = Field(default_factory=DetectorSettings)

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
    def load(
        cls,
        *,
        config_package_dir: Path | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        dotenv_path: Path | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> "Settings":
        """Load settings from TOML + dotenv + env vars + explicit overrides."""

        cwd = cwd or Path.cwd()
        env = env or os.environ
        overrides_dict = dict(overrides or {})

        cwd_toml = _load_settings_toml(cwd / "settings.toml")
        dotenv_env = _load_dotenv(dotenv_path or (cwd / ".env"))

        def parse_prefixed(source: Mapping[str, str]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for key, value in source.items():
                if not key.startswith(ENV_PREFIX):
                    continue
                field = key[len(ENV_PREFIX) :].lower()
                if field in cls.model_fields:
                    out[field] = value
            return out

        dotenv_settings = parse_prefixed(dotenv_env)
        env_settings = parse_prefixed(env)

        # Resolve config package directory for settings.toml discovery.
        cfg_dir: Path | None = None
        if config_package_dir is not None:
            cfg_dir = Path(config_package_dir).expanduser().resolve()
        elif "config_package" in overrides_dict and overrides_dict["config_package"]:
            cfg_dir = Path(str(overrides_dict["config_package"])).expanduser().resolve()
        elif env_settings.get("config_package"):
            cfg_dir = Path(str(env_settings["config_package"])).expanduser().resolve()
        elif dotenv_settings.get("config_package"):
            cfg_dir = Path(str(dotenv_settings["config_package"])).expanduser().resolve()
        elif cwd_toml.get("config_package"):
            cfg_dir = Path(str(cwd_toml["config_package"])).expanduser().resolve()

        cfg_toml: dict[str, Any] = {}
        if cfg_dir is not None:
            cfg_toml = _load_settings_toml(cfg_dir / "settings.toml")

        data: dict[str, Any] = {}
        data.update(cwd_toml)
        data.update(cfg_toml)
        data.update(dotenv_settings)
        data.update(env_settings)
        data.update(overrides_dict)

        if cfg_dir is not None:
            # Keep the stored config_package normalized if we resolved it.
            data["config_package"] = str(cfg_dir)

        return cls.model_validate(data)


__all__ = ["ENV_PREFIX", "Settings"]
