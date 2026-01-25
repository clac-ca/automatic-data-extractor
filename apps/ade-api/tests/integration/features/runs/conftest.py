from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


@pytest.fixture()
def session(db_session: Session) -> Session:
    """Provide an isolated database session for run tests."""
    return db_session
