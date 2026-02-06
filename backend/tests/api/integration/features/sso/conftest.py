from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from ade_api.settings import Settings


@pytest.fixture()
def session(db_session: Session) -> Session:
    return db_session


@pytest.fixture()
def settings(base_settings: Settings) -> Settings:
    payload = base_settings.model_dump()
    payload["sso_encryption_key"] = "test-sso-encryption-key"
    return Settings.model_validate(payload)
