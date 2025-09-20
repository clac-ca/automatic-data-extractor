"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from . import config
from .auth.validation import validate_settings
from .db_migrations import SchemaState, ensure_schema
from .maintenance import AutoPurgeScheduler
from .routes.auth import router as auth_router
from .routes.health import router as health_router
from .routes.configurations import (
    router as configurations_router,
)
from .routes.jobs import router as jobs_router
from .routes.documents import router as documents_router
from .routes.events import router as events_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare filesystem directories and database tables."""

    settings = config.get_settings()
    validate_settings(settings)
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    documents_dir: Path = settings.documents_dir
    documents_dir.mkdir(parents=True, exist_ok=True)
    (documents_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (documents_dir / "output").mkdir(parents=True, exist_ok=True)

    logger.info(
        "Resolved storage paths",
        extra={
            "data_dir": str(settings.data_dir),
            "documents_dir": str(documents_dir),
            "database_url": settings.database_url,
        },
    )

    schema_state: SchemaState = ensure_schema()
    if schema_state == "migrated":
        logger.info("Database migrations applied automatically")
    elif schema_state == "metadata_created":
        logger.info("Initialised in-memory database for this session")
    else:
        logger.info("Database schema already current; migrations skipped")

    scheduler = AutoPurgeScheduler()
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(title="Automatic Data Extractor", lifespan=lifespan)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(configurations_router)
app.include_router(jobs_router)
app.include_router(documents_router)
app.include_router(events_router)


__all__ = ["app"]
