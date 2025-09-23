"""Dependency helpers for the users module."""

from __future__ import annotations

from ...core.service import service_dependency
from .service import UsersService


get_users_service = service_dependency(UsersService)


__all__ = ["get_users_service"]
