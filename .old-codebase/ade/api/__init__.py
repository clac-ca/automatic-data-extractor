"""ADE API shell exposing error handlers and settings dependency."""

from .errors import register_exception_handlers
from .settings import get_app_settings

__all__ = ["register_exception_handlers", "get_app_settings"]
