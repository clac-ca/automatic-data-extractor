"""FastAPI dependencies for the jobs module."""

from __future__ import annotations

from ...core.service import service_dependency
from .service import JobsService


get_jobs_service = service_dependency(JobsService)


__all__ = ["get_jobs_service"]
