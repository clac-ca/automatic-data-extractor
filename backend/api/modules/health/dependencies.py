"""Dependency injection helpers for the health module."""

from __future__ import annotations

from ...core.service import service_dependency
from .service import HealthService

get_health_service = service_dependency(HealthService)
