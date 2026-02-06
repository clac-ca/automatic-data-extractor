"""Shared constants for configuration package IO and validation."""

from __future__ import annotations

CONFIG_DEP_FILES = (
    "pyproject.toml",
    "poetry.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.in",
    "constraints.txt",
)

CONFIG_EXCLUDED_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "__MACOSX",
}

CONFIG_EXCLUDED_SUFFIXES = {".pyc"}
CONFIG_IGNORED_FILENAMES = {".DS_Store"}

CONFIG_COPY_IGNORE_PATTERNS = (
    *sorted(CONFIG_EXCLUDED_NAMES),
    "*.pyc",
    ".DS_Store",
)
