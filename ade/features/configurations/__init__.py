"""Configurations module exposing read-only endpoints and services."""

from .router import router
from .schemas import ConfigurationRecord
from .service import ConfigurationsService

__all__ = [
    "ConfigurationRecord",
    "ConfigurationsService",
    "router",
]
