"""FastAPI dependencies for the extraction results module."""

from __future__ import annotations

from ...core.service import service_dependency
from .service import ExtractionResultsService

get_results_service = service_dependency(ExtractionResultsService)


__all__ = ["get_results_service"]
