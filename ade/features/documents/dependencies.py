"""FastAPI dependencies for the documents feature."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ade.api.settings import get_app_settings
from ade.db.session import get_session
from ade.platform.config import Settings

from .service import DocumentsService


async def get_documents_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> DocumentsService:
    """Construct a ``DocumentsService`` for request-scoped operations."""

    return DocumentsService(session=session, settings=settings)


__all__ = ["get_documents_service"]
