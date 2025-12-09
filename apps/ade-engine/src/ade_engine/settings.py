"""Minimal engine settings (external to the manifest)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

DEFAULT_CONFIG_PACKAGE = "ade_config"
DEFAULT_SUPPORTED_FILE_EXTENSIONS: tuple[str, ...] = ("*.xlsx", "*.csv")
DEFAULT_LOG_FORMAT = "text"


@dataclass(frozen=True)
class Settings:
    """External defaults; pipeline behavior comes from the config manifest."""

    config_package: str = DEFAULT_CONFIG_PACKAGE
    supported_file_extensions: tuple[str, ...] = DEFAULT_SUPPORTED_FILE_EXTENSIONS
    log_level: int = logging.INFO
    log_format: str = DEFAULT_LOG_FORMAT


__all__ = ["Settings"]
