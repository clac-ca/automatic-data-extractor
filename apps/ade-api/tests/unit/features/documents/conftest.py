from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from ade_api.db import Base, DatabaseSettings, build_engine
from ade_api.settings import Settings


@pytest.fixture()
def session() -> Session:
    engine = build_engine(DatabaseSettings(url="sqlite:///:memory:"))
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def settings() -> Settings:
    return Settings(jwt_secret="test-jwt-secret-for-tests-please-change")
