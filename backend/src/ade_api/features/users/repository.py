"""Query helpers for working with ``User`` records."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ade_db.models import User


def _canonical_email(value: str) -> str:
    return value.strip().lower()


_UNSET = object()


class UsersRepository:
    """High-level persistence helpers for the unified user model."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: str | UUID) -> User | None:
        stmt = select(User).options(selectinload(User.oauth_accounts)).where(User.id == user_id)
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_id_basic(self, user_id: str | UUID) -> User | None:
        """Lightweight lookup without eager-loading relationships."""

        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.oauth_accounts))
            .where(User.email_normalized == _canonical_email(email))
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.email_normalized)
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def create(
        self,
        *,
        email: str,
        hashed_password: str,
        display_name: str | None = None,
        is_active: bool = True,
        is_service_account: bool = False,
        is_verified: bool = True,
        must_change_password: bool = False,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            display_name=display_name,
            is_active=is_active,
            is_service_account=is_service_account,
            is_verified=is_verified,
            must_change_password=must_change_password,
            failed_login_count=0,
        )
        self._session.add(user)
        self._session.flush()
        self._session.refresh(user)
        return user

    def set_password(self, user: User, password_hash: str) -> User:
        user.hashed_password = password_hash
        self._session.flush()
        self._session.refresh(user)
        return user

    def update_user(
        self,
        user: User,
        *,
        display_name: str | None | object = _UNSET,
        is_active: bool | None | object = _UNSET,
    ) -> User:
        if display_name is not _UNSET:
            user.display_name = cast(str | None, display_name)
        if is_active is not _UNSET:
            user.is_active = cast(bool, is_active)
        self._session.flush()
        self._session.refresh(user)
        return user


__all__ = ["UsersRepository"]
