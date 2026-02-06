"""Centralized CLI applications for ADE services."""

from .main import ade_api_app, ade_app, ade_db_app, ade_storage_app, ade_worker_app

__all__ = [
    "ade_app",
    "ade_api_app",
    "ade_worker_app",
    "ade_db_app",
    "ade_storage_app",
]
