from __future__ import annotations

import pytest

from backend.app.shared.db.session import get_sessionmaker
from backend.app.features.roles.authorization import authorize
from backend.app.features.roles.service import AuthorizationError, ensure_user_principal
from backend.app.features.users.models import User

pytestmark = pytest.mark.asyncio


async def _principal_id(session, user_id: str) -> str:
    user = await session.get(User, user_id)
    assert user is not None
    principal = await ensure_user_principal(session=session, user=user)
    return principal.id


async def test_authorize_global_allows_admin(seed_identity: dict[str, object]) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        admin = seed_identity["admin"]
        principal_id = await _principal_id(session, admin["id"])  # type: ignore[index]
        decision = await authorize(
            session=session,
            principal_id=principal_id,
            permission_key="Workspaces.Create",
        )
    assert decision.is_authorized


async def test_authorize_workspace_rejects_missing_scope(seed_identity: dict[str, object]) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        member = seed_identity["member"]
        principal_id = await _principal_id(session, member["id"])  # type: ignore[index]
        with pytest.raises(AuthorizationError):
            await authorize(
                session=session,
                principal_id=principal_id,
                permission_key="Workspace.Members.Read",
                scope_type="workspace",
            )


async def test_authorize_workspace_checks_permissions(
    seed_identity: dict[str, object]
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        owner = seed_identity["workspace_owner"]
        owner_principal_id = await _principal_id(session, owner["id"])  # type: ignore[index]
        decision = await authorize(
            session=session,
            principal_id=owner_principal_id,
            permission_key="Workspace.Members.ReadWrite",
            scope_type="workspace",
            scope_id=seed_identity["workspace_id"],  # type: ignore[index]
        )
    assert decision.is_authorized

    async with session_factory() as session:
        member = seed_identity["member"]
        member_principal_id = await _principal_id(session, member["id"])  # type: ignore[index]
        decision = await authorize(
            session=session,
            principal_id=member_principal_id,
            permission_key="Workspace.Members.ReadWrite",
            scope_type="workspace",
            scope_id=seed_identity["workspace_id"],  # type: ignore[index]
        )
    assert not decision.is_authorized
