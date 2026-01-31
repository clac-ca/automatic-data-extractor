from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


@pytest.fixture()
def session(db_session: Session) -> Session:
    return db_session
