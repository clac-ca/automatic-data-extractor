from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import APIKey


class APIKeysRepository:
    """Persistence helpers for ``APIKey`` records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: str,
        token_prefix: str,
        token_hash: str,
        expires_at: datetime | None,
        label: str | None,
    ) -> APIKey:
        api_key = APIKey(
            user_id=user_id,
            token_prefix=token_prefix,
            token_hash=token_hash,
            expires_at=expires_at,
            label=label,
        )
        self._session.add(api_key)
        await self._session.flush()
        await self._session.refresh(api_key)
        return api_key

    async def list_api_keys(self, *, include_revoked: bool = False) -> list[APIKey]:
        stmt = (
            select(APIKey)
            .options(selectinload(APIKey.user))
            .order_by(APIKey.created_at.desc())
        )
        if not include_revoked:
            stmt = stmt.where(APIKey.revoked_at.is_(None))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_prefix(self, token_prefix: str) -> APIKey | None:
        stmt = (
            select(APIKey)
            .options(selectinload(APIKey.user))
            .where(
                APIKey.token_prefix == token_prefix,
                APIKey.revoked_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, api_key_id: str) -> APIKey | None:
        stmt = (
            select(APIKey)
            .options(selectinload(APIKey.user))
            .where(APIKey.id == api_key_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, api_key: APIKey, *, revoked_at: datetime) -> APIKey:
        api_key.revoked_at = revoked_at
        await self._session.flush()
        await self._session.refresh(api_key)
        return api_key


__all__ = ["APIKeysRepository"]
