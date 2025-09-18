"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from . import config
from .db import Base, get_engine
from .routes.health import router as health_router
from .routes.configuration_revisions import (
    router as configuration_revisions_router,
)
from .routes.jobs import router as jobs_router
from .routes.documents import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare filesystem directories and database tables."""

    settings = config.get_settings()
    documents_dir: Path = settings.documents_dir
    documents_dir.mkdir(parents=True, exist_ok=True)

    db_path: Path | None = settings.database_path
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Import models so SQLAlchemy is aware of the tables before create_all
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    yield


app = FastAPI(title="Automatic Data Extractor", lifespan=lifespan)
app.include_router(health_router)
app.include_router(configuration_revisions_router)
app.include_router(jobs_router)
app.include_router(documents_router)


__all__ = ["app"]
