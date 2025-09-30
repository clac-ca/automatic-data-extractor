"""Configurations module exposing read-only endpoints and services."""

from .dependencies import get_configurations_service
from .router import router
from .schemas import ConfigurationRecord
from .service import ConfigurationsService

__all__ = [
    "ConfigurationRecord",
    "ConfigurationsService",
    "get_configurations_service",
    "router",
]
