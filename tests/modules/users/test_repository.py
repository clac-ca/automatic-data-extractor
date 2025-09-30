"""Tests for the user repository helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.db.session import get_sessionmaker
from app.users.models import User
from app.users.repository import UsersRepository


@pytest.mark.asyncio
async def test_create_and_list_service_accounts() -> None:
    """Repository should persist and list service-account users."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = UsersRepository(session)

        human = await repo.create(
            email=f"{uuid4().hex}@example.com",
            password_hash="secret",
        )

        account = await repo.create(
            email=f"automation-{uuid4().hex}@service.local",
            display_name=" Automated Bot ",
            description="  Handles integration tasks  ",
            created_by_user_id=human.id,
            is_service_account=True,
        )

        assert account.is_service_account is True
        assert account.password_hash is None
        assert account.display_name == "Automated Bot"
        assert account.description == "Handles integration tasks"
        assert account.label == "Automated Bot"

        listed = await repo.list_service_accounts()
        assert account.id in {record.id for record in listed}
        assert all(record.is_service_account for record in listed)

        fetched = await repo.get_by_email(account.email_canonical)
        assert fetched is not None
        assert fetched.id == account.id


@pytest.mark.asyncio
async def test_service_account_password_validation() -> None:
    """Assigning a password to a service account should error."""

    with pytest.raises(ValueError):
        User(
            email=f"automation-{uuid4().hex}@service.local",
            is_service_account=True,
            password_hash="not-allowed",
        )
