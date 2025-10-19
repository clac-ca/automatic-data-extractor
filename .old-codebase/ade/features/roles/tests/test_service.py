from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from ade.db.session import get_sessionmaker
from ade.features.roles import registry
from ade.features.roles.models import (
    Permission,
    Principal,
    Role,
    RoleAssignment,
    RolePermission,
)
from ade.features.roles.service import (
    AuthorizationError,
    assign_global_role,
    authorize_global,
    authorize_workspace,
    collect_permission_keys,
    get_global_permissions_for_user,
    RoleScopeMismatchError,
    sync_permission_registry,
)
from ade.features.users.models import User


def test_collect_permission_keys_rejects_unknown() -> None:
    with pytest.raises(AuthorizationError):
        collect_permission_keys(["Workspace.Unknown"],)


def test_authorize_workspace_default_deny() -> None:
    decision = authorize_workspace(
        granted=["Workspace.Documents.Read"],
        required=["Workspace.Documents.ReadWrite"],
    )

    assert not decision.is_authorized
    assert decision.missing == ("Workspace.Documents.ReadWrite",)


def test_authorize_workspace_implications_allow_readwrite() -> None:
    decision = authorize_workspace(
        granted=["Workspace.Members.ReadWrite"],
        required=(
            "Workspace.Read",
            "Workspace.Members.Read",
            "Workspace.Members.ReadWrite",
        ),
    )

    assert decision.is_authorized


def test_authorize_workspace_any_permission_implies_read() -> None:
    decision = authorize_workspace(
        granted=["Workspace.Documents.ReadWrite"],
        required=["Workspace.Read"],
    )

    assert decision.is_authorized


def test_authorize_global_rejects_workspace_scope() -> None:
    with pytest.raises(AuthorizationError):
        authorize_global(
            granted=["Workspaces.Read.All"],
            required=["Workspace.Members.ReadWrite"],
        )


def test_authorize_global_implications_allow_readwrite() -> None:
    decision = authorize_global(
        granted=["Roles.ReadWrite.All"],
        required=["Roles.Read.All"],
    )

    assert decision.is_authorized


@pytest.mark.asyncio
async def test_get_global_permissions_for_admin(
    seed_identity: dict[str, object]
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        admin_id = seed_identity["admin"]["id"]  # type: ignore[index]
        admin = await session.get(User, admin_id)
        assert admin is not None

        permissions = await get_global_permissions_for_user(session=session, user=admin)

    assert "Workspaces.Create" in permissions
    assert registry.PERMISSION_REGISTRY["Workspaces.Read.All"].key in permissions


@pytest.mark.asyncio
async def test_sync_permission_registry_is_idempotent() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await session.execute(delete(RolePermission))
        await session.execute(delete(Role))
        await session.execute(delete(Permission))
        await session.commit()

    async with session_factory() as session:
        await sync_permission_registry(session=session)

    async with session_factory() as session:
        result = await session.execute(select(Permission.key))
        permission_keys = set(result.scalars().all())
        assert permission_keys == {definition.key for definition in registry.PERMISSIONS}

        result = await session.execute(select(Role.slug))
        role_slugs = set(result.scalars().all())
        assert role_slugs == {definition.slug for definition in registry.SYSTEM_ROLES}

        result = await session.execute(select(RolePermission))
        role_permission_rows = list(result.scalars().all())
        assert role_permission_rows


@pytest.mark.asyncio
async def test_role_updated_at_advances_on_update() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        role = Role(
            slug="test-role",
            name="Test Role",
            scope_type="global",
            scope_id=None,
            description="",
            built_in=False,
            editable=True,
        )
        session.add(role)
        await session.flush()

        original_updated_at = role.updated_at

        role.name = "Test Role Updated"
        await session.flush()
        await session.refresh(role)

        def _normalize(value: datetime) -> datetime:
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        assert _normalize(role.updated_at) >= _normalize(original_updated_at)
        assert role.updated_at != original_updated_at

        await session.delete(role)
        await session.commit()


@pytest.mark.asyncio
async def test_assign_global_role_rejects_workspace_role(
    seed_identity: dict[str, object],
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await sync_permission_registry(session=session)

    async with session_factory() as session:
        workspace_role = (
            await session.execute(
                select(Role).where(
                    Role.slug == "workspace-owner",
                    Role.scope_type == "workspace",
                )
            )
        ).scalar_one()

        with pytest.raises(RoleScopeMismatchError):
            await assign_global_role(
                session=session,
                user_id=seed_identity["member"]["id"],  # type: ignore[index]
                role_id=workspace_role.id,
            )


@pytest.mark.asyncio
async def test_assign_global_role_succeeds_for_global_scope(
    seed_identity: dict[str, object],
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await sync_permission_registry(session=session)

    async with session_factory() as session:
        global_role = (
            await session.execute(
                select(Role).where(
                    Role.slug == "global-administrator",
                    Role.scope_type == "global",
                    Role.scope_id.is_(None),
                )
            )
        ).scalar_one()

        user_id = seed_identity["member"]["id"]  # type: ignore[index]

        await assign_global_role(
            session=session,
            user_id=user_id,
            role_id=global_role.id,
        )

        principal = (
            await session.execute(
                select(Principal).where(Principal.user_id == user_id)
            )
        ).scalar_one()

        result = await session.execute(
            select(RoleAssignment).where(
                RoleAssignment.principal_id == principal.id,
                RoleAssignment.scope_type == "global",
            )
        )
        assignments = result.scalars().all()
        assert any(assignment.role_id == global_role.id for assignment in assignments)

        await session.execute(
            delete(RoleAssignment).where(
                RoleAssignment.principal_id == principal.id
            )
        )
        await session.execute(
            delete(Principal).where(Principal.id == principal.id)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_assign_global_role_is_idempotent(
    seed_identity: dict[str, object],
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await sync_permission_registry(session=session)

    async with session_factory() as session:
        global_role = (
            await session.execute(
                select(Role).where(
                    Role.slug == "global-administrator",
                    Role.scope_type == "global",
                    Role.scope_id.is_(None),
                )
            )
        ).scalar_one()

        user_id = seed_identity["admin"]["id"]  # type: ignore[index]

        first_assignment = await assign_global_role(
            session=session,
            user_id=user_id,
            role_id=global_role.id,
        )
        second_assignment = await assign_global_role(
            session=session,
            user_id=user_id,
            role_id=global_role.id,
        )

        assert first_assignment.id == second_assignment.id

        stored_assignments = (
            await session.execute(
                select(RoleAssignment).where(
                    RoleAssignment.principal_id == first_assignment.principal_id,
                    RoleAssignment.role_id == global_role.id,
                    RoleAssignment.scope_type == "global",
                    RoleAssignment.scope_id.is_(None),
                )
            )
        ).scalars().all()

        assert len(stored_assignments) == 1
