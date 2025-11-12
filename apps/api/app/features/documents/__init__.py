"""Documents module scaffolding for the backend rewrite."""

from . import router
from .storage import DocumentStorage, StoredDocument

__all__ = ["router", "DocumentStorage", "StoredDocument"]
