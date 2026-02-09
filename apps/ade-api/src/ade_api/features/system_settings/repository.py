"""Helpers for reading and mutating system settings."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.models import SystemSetting


class SystemSettingsRepository:
    """Simple persistence helpers for ``SystemSetting`` records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> SystemSetting | None:
        stmt = select(SystemSetting).where(SystemSetting.key == key).limit(1)
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_for_update(self, key: str) -> SystemSetting | None:
        stmt = select(SystemSetting).where(SystemSetting.key == key).with_for_update(nowait=False)
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def create(self, *, key: str, value: Mapping[str, object] | None = None) -> SystemSetting:
        setting = SystemSetting(key=key, value=dict(value or {}))
        self._session.add(setting)
        self._session.flush()
        return setting


__all__ = ["SystemSettingsRepository"]
