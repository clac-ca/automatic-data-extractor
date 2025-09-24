"""FastAPI dependencies for the configurations module."""

from __future__ import annotations

from ...core.service import service_dependency
from .service import ConfigurationsService


get_configurations_service = service_dependency(ConfigurationsService)


__all__ = ["get_configurations_service"]
