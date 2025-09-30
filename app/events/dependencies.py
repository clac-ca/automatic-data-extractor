"""FastAPI dependencies for the events module."""

from __future__ import annotations

from app.core.service import service_dependency
from .service import EventsService

get_events_service = service_dependency(EventsService)


__all__ = ["get_events_service"]
