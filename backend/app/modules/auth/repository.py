from __future__ import annotations

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
        user_id: str | None,
        service_account_id: str | None,
        token_prefix: str,
        token_hash: str,
        expires_at: str | None,
    ) -> APIKey:
        api_key = APIKey(
            user_id=user_id,
            service_account_id=service_account_id,
            token_prefix=token_prefix,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(api_key)
        await self._session.flush()
        await self._session.refresh(api_key)
        return api_key

    async def list_api_keys(self) -> list[APIKey]:
        stmt = (
            select(APIKey)
            .options(
                selectinload(APIKey.user),
                selectinload(APIKey.service_account),
            )
            .order_by(APIKey.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_prefix(self, token_prefix: str) -> APIKey | None:
        stmt = (
            select(APIKey)
            .options(selectinload(APIKey.user), selectinload(APIKey.service_account))
            .where(APIKey.token_prefix == token_prefix)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, api_key_id: str) -> APIKey | None:
        stmt = (
            select(APIKey)
            .options(selectinload(APIKey.user), selectinload(APIKey.service_account))
            .where(APIKey.id == api_key_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, api_key: APIKey) -> None:
        await self._session.delete(api_key)


__all__ = ["APIKeysRepository"]
