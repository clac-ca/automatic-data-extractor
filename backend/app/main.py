"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI

from .config import get_settings
from .db import Base, engine
from .routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare filesystem directories and database tables."""

    settings = get_settings()
    documents_dir = settings.documents_dir
    documents_dir.parent.mkdir(parents=True, exist_ok=True)
    documents_dir.mkdir(parents=True, exist_ok=True)

    db_path: Optional[Path]
    try:
        db_path = settings.database_path
    except ValueError:
        db_path = None
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Import models so SQLAlchemy is aware of the tables before create_all
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Automatic Data Extractor", lifespan=lifespan)
app.include_router(health_router)


__all__ = ["app"]
