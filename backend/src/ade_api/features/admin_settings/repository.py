"""Persistence helpers for singleton application runtime settings."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_db.models import ApplicationSetting

APPLICATION_SETTINGS_SINGLETON_ID = 1


class ApplicationSettingsRepository:
    """Read/write helpers for the singleton ``ApplicationSetting`` row."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> ApplicationSetting | None:
        return self._session.get(ApplicationSetting, APPLICATION_SETTINGS_SINGLETON_ID)

    def get_for_update(self) -> ApplicationSetting | None:
        stmt = (
            select(ApplicationSetting)
            .where(ApplicationSetting.id == APPLICATION_SETTINGS_SINGLETON_ID)
            .with_for_update(nowait=False)
        )
        return self._session.execute(stmt).scalar_one_or_none()


__all__ = [
    "APPLICATION_SETTINGS_SINGLETON_ID",
    "ApplicationSettingsRepository",
]
