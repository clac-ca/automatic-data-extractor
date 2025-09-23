"""Repository helpers for user persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


class UsersRepository:
    """Persistence operations for ``User`` records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email_canonical: str) -> User | None:
        stmt = select(User).where(User.email_canonical == email_canonical)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sso_identity(self, provider: str, subject: str) -> User | None:
        stmt = select(User).where(
            User.sso_provider == provider, User.sso_subject == subject
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.email_canonical)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["UsersRepository"]
