"""ADE API shell exposing error handlers and settings dependency."""

from ..shared.core.config import get_app_settings
from ..shared.core.errors import register_exception_handlers

__all__ = ["register_exception_handlers", "get_app_settings"]
