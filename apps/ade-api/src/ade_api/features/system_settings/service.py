"""Service layer for system setting CRUD."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.settings import Settings
from ade_api.shared.core.logging import log_context

from .models import SystemSetting
from .schemas import SafeModeStatus

logger = logging.getLogger(__name__)

SAFE_MODE_SETTING_KEY = "safe-mode"
SAFE_MODE_DEFAULT_DETAIL = (
    "ADE safe mode enabled; skipping engine execution until ADE_SAFE_MODE is disabled."
)


class SystemSettingsService:
    """Simple CRUD helpers for system settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> dict[str, Any] | None:
        logger.debug(
            "system_settings.get.start",
            extra=log_context(setting_key=key),
        )
        record = await self._fetch_by_key(key)
        value = dict(record.value) if record else None
        logger.debug(
            "system_settings.get.result",
            extra=log_context(
                setting_key=key,
                found=record is not None,
            ),
        )
        return value

    async def upsert(self, key: str, value: dict[str, Any]) -> SystemSetting:
        logger.debug(
            "system_settings.upsert.start",
            extra=log_context(setting_key=key),
        )
        setting = await self._fetch_by_key(key)
        created = setting is None

        if setting is None:
            setting = SystemSetting(key=key, value=dict(value))
            self._session.add(setting)
        else:
            setting.value = dict(value)

        await self._session.flush()

        logger.info(
            "system_settings.upsert.success",
            extra=log_context(
                setting_key=key,
                record_created=created,
            ),
        )
        return setting

    async def delete(self, key: str) -> None:
        logger.debug(
            "system_settings.delete.start",
            extra=log_context(setting_key=key),
        )
        setting = await self._fetch_by_key(key)
        if setting is not None:
            await self._session.delete(setting)
            await self._session.flush()
            logger.info(
                "system_settings.delete.success",
                extra=log_context(setting_key=key),
            )
        else:
            logger.debug(
                "system_settings.delete.not_found",
                extra=log_context(setting_key=key),
            )

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

        logger.debug("safe_mode.get_status.start", extra=log_context())
        persisted = await self._system_settings.get(SAFE_MODE_SETTING_KEY)

        enabled = self._settings.safe_mode
        detail = SAFE_MODE_DEFAULT_DETAIL
        if persisted is not None:
            enabled = bool(persisted.get("enabled", enabled))
            detail = str(persisted.get("detail") or detail)

        status = SafeModeStatus(enabled=enabled, detail=detail)

        logger.info(
            "safe_mode.get_status.result",
            extra=log_context(
                safe_mode_enabled=status.enabled,
                persisted_overridden=persisted is not None,
            ),
        )
        return status

    async def update_status(
        self,
        *,
        enabled: bool,
        detail: str | None = None,
    ) -> SafeModeStatus:
        """Persist the safe mode state and return the normalized value."""

        logger.debug(
            "safe_mode.update_status.start",
            extra=log_context(
                safe_mode_enabled=enabled,
            ),
        )

        normalized_detail = (detail or "").strip() or SAFE_MODE_DEFAULT_DETAIL
        record = await self._system_settings._fetch_by_key(SAFE_MODE_SETTING_KEY)
        payload = {"enabled": enabled, "detail": normalized_detail}
        created = record is None

        if record is None:
            record = SystemSetting(key=SAFE_MODE_SETTING_KEY, value=payload)
            self._session.add(record)
        else:
            record.value = payload

        await self._session.flush()
        await self._session.commit()

        status = SafeModeStatus(enabled=enabled, detail=normalized_detail)

        logger.info(
            "safe_mode.update_status.success",
            extra=log_context(
                safe_mode_enabled=status.enabled,
                record_created=created,
                detail_overridden=bool(detail and detail.strip()),
            ),
        )

        return status


__all__ = [
    "SAFE_MODE_DEFAULT_DETAIL",
    "SAFE_MODE_SETTING_KEY",
    "SafeModeService",
    "SystemSettingsService",
]
