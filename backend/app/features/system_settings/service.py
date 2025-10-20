"""Service layer for system setting CRUD."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .models import SystemSetting


class SystemSettingsService:
    """Simple CRUD helpers for system settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> dict[str, Any] | None:
        record = await self._session.get(SystemSetting, key)
        return dict(record.value) if record else None

    async def upsert(self, key: str, value: dict[str, Any]) -> SystemSetting:
        setting = await self._session.get(SystemSetting, key)
        if setting is None:
            setting = SystemSetting(key=key, value=dict(value))
            self._session.add(setting)
        else:
            setting.value = dict(value)
        await self._session.flush()
        return setting

    async def delete(self, key: str) -> None:
        setting = await self._session.get(SystemSetting, key)
        if setting is not None:
            await self._session.delete(setting)
            await self._session.flush()


__all__ = ["SystemSettingsService"]
