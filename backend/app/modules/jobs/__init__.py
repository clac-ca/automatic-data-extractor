"""Jobs module exposing read-only endpoints and services."""

from .dependencies import get_jobs_service
from .router import router
from .schemas import JobRecord
from .service import JobsService
from .worker import register_job_queue_handlers

__all__ = [
    "JobRecord",
    "JobsService",
    "get_jobs_service",
    "register_job_queue_handlers",
    "router",
]
