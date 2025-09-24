from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ServiceAccount


class ServiceAccountsRepository:
    """Persistence helpers for ``ServiceAccount`` records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        display_name: str,
        description: str | None = None,
        created_by_user_id: str | None = None,
    ) -> ServiceAccount:
        record = ServiceAccount(
            name=name,
            display_name=display_name,
            description=description,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def get_by_id(self, service_account_id: str) -> ServiceAccount | None:
        stmt = select(ServiceAccount).where(ServiceAccount.id == service_account_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[ServiceAccount]:
        stmt = (
            select(ServiceAccount)
            .where(ServiceAccount.is_active.is_(True))
            .order_by(ServiceAccount.display_name.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["ServiceAccountsRepository"]
