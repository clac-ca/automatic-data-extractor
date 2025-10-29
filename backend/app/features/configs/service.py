"""Placeholder service for configuration engine v0.4 implementation."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class ConfigService:
    """Service surface for upcoming file-backed configuration engine."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session


__all__ = ["ConfigService"]
