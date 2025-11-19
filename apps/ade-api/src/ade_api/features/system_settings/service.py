"""Service layer for system setting CRUD."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.settings import Settings

from .models import SystemSetting
from .schemas import SafeModeStatus


SAFE_MODE_SETTING_KEY = "safe-mode"
SAFE_MODE_DEFAULT_DETAIL = (
    "ADE safe mode enabled; skipping engine execution until ADE_SAFE_MODE is disabled."
)


class SystemSettingsService:
    """Simple CRUD helpers for system settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> dict[str, Any] | None:
        record = await self._fetch_by_key(key)
        return dict(record.value) if record else None

    async def upsert(self, key: str, value: dict[str, Any]) -> SystemSetting:
        setting = await self._fetch_by_key(key)
        if setting is None:
            setting = SystemSetting(key=key, value=dict(value))
            self._session.add(setting)
        else:
            setting.value = dict(value)
        await self._session.flush()
        return setting

    async def delete(self, key: str) -> None:
        setting = await self._fetch_by_key(key)
        if setting is not None:
            await self._session.delete(setting)
            await self._session.flush()

    async def _fetch_by_key(self, key: str) -> SystemSetting | None:
        stmt = select(SystemSetting).where(SystemSetting.key == key).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class SafeModeService:
    """Persist and fetch ADE safe mode state."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._system_settings = SystemSettingsService(session=session)

    async def get_status(self) -> SafeModeStatus:
        """Return the current safe mode state, applying persisted overrides if present."""

        persisted = await self._system_settings.get(SAFE_MODE_SETTING_KEY)
        enabled = self._settings.safe_mode
        detail = SAFE_MODE_DEFAULT_DETAIL
        if persisted is not None:
            enabled = bool(persisted.get("enabled", enabled))
            detail = str(persisted.get("detail") or detail)
        return SafeModeStatus(enabled=enabled, detail=detail)

    async def update_status(self, *, enabled: bool, detail: str | None = None) -> SafeModeStatus:
        """Persist the safe mode state and return the normalized value."""

        normalized_detail = (detail or "").strip() or SAFE_MODE_DEFAULT_DETAIL
        async with self._session.begin():
            record = await self._system_settings._fetch_by_key(SAFE_MODE_SETTING_KEY)
            payload = {"enabled": enabled, "detail": normalized_detail}
            if record is None:
                record = SystemSetting(key=SAFE_MODE_SETTING_KEY, value=payload)
                self._session.add(record)
            else:
                record.value = payload
            await self._session.flush()

        return SafeModeStatus(enabled=enabled, detail=normalized_detail)


__all__ = [
    "SAFE_MODE_DEFAULT_DETAIL",
    "SAFE_MODE_SETTING_KEY",
    "SafeModeService",
    "SystemSettingsService",
]
