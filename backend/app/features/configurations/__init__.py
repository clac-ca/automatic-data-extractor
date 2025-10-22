"""Configurations module exposing read-only endpoints and services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from .router import router
    from .schemas import ConfigurationRecord
    from .service import ConfigurationsService

__all__ = ["ConfigurationRecord", "ConfigurationsService", "router"]


def __getattr__(name: str) -> Any:
    if name == "router":
        from .router import router as _router

        return _router
    if name == "ConfigurationRecord":
        from .schemas import ConfigurationRecord as _record

        return _record
    if name == "ConfigurationsService":
        from .service import ConfigurationsService as _service

        return _service
    raise AttributeError(name)
