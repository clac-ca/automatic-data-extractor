"""
Temporary shim to keep imports stable while the auth feature is rewritten.

All existing imports from ``ade_api.features.auth`` are forwarded to the
legacy implementation in ``ade_api.features.auth_legacy``.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING

_LEGACY_PACKAGE = "ade_api.features.auth_legacy"
_ALIAS_MODULES = [
    "models",
    "repository",
    "router",
    "schemas",
    "security",
    "service",
    "utils",
]


def _alias_module(name: str) -> ModuleType:
    module = importlib.import_module(f"{_LEGACY_PACKAGE}.{name}")
    sys.modules[f"{__name__}.{name}"] = module
    return module


for _module_name in _ALIAS_MODULES:
    globals()[_module_name] = _alias_module(_module_name)

if TYPE_CHECKING:
    from ade_api.features import auth_legacy

    models = auth_legacy.models
    repository = auth_legacy.repository
    router = auth_legacy.router
    schemas = auth_legacy.schemas
    security = auth_legacy.security
    service = auth_legacy.service
    utils = auth_legacy.utils

__all__ = ["models", "repository", "router", "schemas", "security", "service", "utils"]
