"""Canonical CLI app exports used by script entry points and wrappers."""

from .api import app as ade_api_app
from .db import app as ade_db_app
from .root import app as ade_app
from .storage import app as ade_storage_app
from .worker import app as ade_worker_app

__all__ = [
    "ade_app",
    "ade_api_app",
    "ade_worker_app",
    "ade_db_app",
    "ade_storage_app",
]
