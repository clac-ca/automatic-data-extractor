"""Events module providing persistence and query helpers."""

from .dependencies import get_events_service
from .schemas import EventRecord
from .service import EventsService

__all__ = [
    "EventsService",
    "EventRecord",
    "get_events_service",
]
