from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from ade_api.settings import Settings
from ade_db.models import (
    ApplicationSetting,
    SsoAuthState,
    SsoProvider,
    SsoProviderDomain,
)


@pytest.fixture()
def session(db_session: Session) -> Session:
    return db_session


@pytest.fixture(autouse=True)
def _reset_sso_runtime_state(session: Session) -> None:
    session.execute(sa.delete(SsoAuthState))
    session.execute(sa.delete(SsoProviderDomain))
    session.execute(sa.delete(SsoProvider))

    record = session.get(ApplicationSetting, 1)
    if record is not None:
        record.data = {}
        record.revision = 1
        record.updated_by = None
    session.flush()


@pytest.fixture()
def settings(base_settings: Settings) -> Settings:
    payload = base_settings.model_dump()
    payload["sso_encryption_key"] = "test-sso-encryption-key"
    return Settings.model_validate(payload)
