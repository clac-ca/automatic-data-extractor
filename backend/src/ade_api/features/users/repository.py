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
        given_name: str | None = None,
        surname: str | None = None,
        job_title: str | None = None,
        department: str | None = None,
        office_location: str | None = None,
        mobile_phone: str | None = None,
        business_phones: str | None = None,
        employee_id: str | None = None,
        employee_type: str | None = None,
        preferred_language: str | None = None,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        source: str = "internal",
        external_id: str | None = None,
        is_active: bool = True,
        is_service_account: bool = False,
        is_verified: bool = True,
        must_change_password: bool = False,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            display_name=display_name,
            given_name=given_name,
            surname=surname,
            job_title=job_title,
            department=department,
            office_location=office_location,
            mobile_phone=mobile_phone,
            business_phones=business_phones,
            employee_id=employee_id,
            employee_type=employee_type,
            preferred_language=preferred_language,
            city=city,
            state=state,
            country=country,
            source=source,
            external_id=external_id,
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
        given_name: str | None | object = _UNSET,
        surname: str | None | object = _UNSET,
        job_title: str | None | object = _UNSET,
        department: str | None | object = _UNSET,
        office_location: str | None | object = _UNSET,
        mobile_phone: str | None | object = _UNSET,
        business_phones: str | None | object = _UNSET,
        employee_id: str | None | object = _UNSET,
        employee_type: str | None | object = _UNSET,
        preferred_language: str | None | object = _UNSET,
        city: str | None | object = _UNSET,
        state: str | None | object = _UNSET,
        country: str | None | object = _UNSET,
        source: str | None | object = _UNSET,
        external_id: str | None | object = _UNSET,
    ) -> User:
        if display_name is not _UNSET:
            user.display_name = cast(str | None, display_name)
        if is_active is not _UNSET:
            user.is_active = cast(bool, is_active)
        if given_name is not _UNSET:
            user.given_name = cast(str | None, given_name)
        if surname is not _UNSET:
            user.surname = cast(str | None, surname)
        if job_title is not _UNSET:
            user.job_title = cast(str | None, job_title)
        if department is not _UNSET:
            user.department = cast(str | None, department)
        if office_location is not _UNSET:
            user.office_location = cast(str | None, office_location)
        if mobile_phone is not _UNSET:
            user.mobile_phone = cast(str | None, mobile_phone)
        if business_phones is not _UNSET:
            user.business_phones = cast(str | None, business_phones)
        if employee_id is not _UNSET:
            user.employee_id = cast(str | None, employee_id)
        if employee_type is not _UNSET:
            user.employee_type = cast(str | None, employee_type)
        if preferred_language is not _UNSET:
            user.preferred_language = cast(str | None, preferred_language)
        if city is not _UNSET:
            user.city = cast(str | None, city)
        if state is not _UNSET:
            user.state = cast(str | None, state)
        if country is not _UNSET:
            user.country = cast(str | None, country)
        if source is not _UNSET:
            user.source = cast(str, source or "internal")
        if external_id is not _UNSET:
            user.external_id = cast(str | None, external_id)
        self._session.flush()
        self._session.refresh(user)
        return user


__all__ = ["UsersRepository"]
