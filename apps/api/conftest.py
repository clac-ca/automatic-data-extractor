"""Shared pytest fixtures for backend tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from apps.api.app.settings import Settings, get_settings, reload_settings
from apps.api.app.shared.db.engine import ensure_database_ready, render_sync_url, reset_database_state
from apps.api.app.shared.db.session import get_sessionmaker
from apps.api.app.features.auth.security import hash_password
from apps.api.app.features.roles.models import Role
from apps.api.app.features.roles.service import (
    assign_global_role,
    assign_role,
    ensure_user_principal,
    sync_permission_registry,
)
from apps.api.app.features.users.models import User, UserCredential
from apps.api.app.features.workspaces.models import Workspace, WorkspaceMembership
from apps.api.app.shared.core.lifecycles import ensure_runtime_dirs
from apps.api.app.shared.dependency import configure_auth_dependencies
from apps.api.app.main import create_app


@pytest.fixture(scope="session")
def _database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Provide a file-backed SQLite database URL for the test session."""

    db_path = tmp_path_factory.mktemp("api-app-db") / "api.sqlite"
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture(scope="session", autouse=True)
def _configure_database(
    _database_url: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[None]:
    """Apply Alembic migrations against the ephemeral test database."""

    data_dir = tmp_path_factory.mktemp("api-app-data")
    documents_dir = data_dir / "documents"
    configs_dir = data_dir / "config_packages"
    venvs_dir = data_dir / ".venv"
    jobs_dir = data_dir / "jobs"
    pip_cache_dir = data_dir / "cache" / "pip"

    os.environ["ADE_DATABASE_DSN"] = _database_url
    os.environ["ADE_DOCUMENTS_DIR"] = str(documents_dir)
    os.environ["ADE_CONFIGS_DIR"] = str(configs_dir)
    os.environ["ADE_VENVS_DIR"] = str(venvs_dir)
    os.environ["ADE_JOBS_DIR"] = str(jobs_dir)
    os.environ["ADE_PIP_CACHE_DIR"] = str(pip_cache_dir)
    # Ensure tests run with OIDC disabled regardless of local .env values.
    os.environ["ADE_OIDC_ENABLED"] = "false"
    os.environ["ADE_SAFE_MODE"] = "false"
    # Explicitly override any .env-provided OIDC settings to disable SSO in tests.
    os.environ["ADE_OIDC_CLIENT_ID"] = ""
    os.environ["ADE_OIDC_CLIENT_SECRET"] = ""
    os.environ["ADE_OIDC_ISSUER"] = ""
    os.environ["ADE_OIDC_REDIRECT_URL"] = ""
    os.environ["ADE_OIDC_SCOPES"] = ""
    settings = reload_settings()
    assert settings.database_dsn == _database_url
    ensure_runtime_dirs(settings)
    reset_database_state()

    config = Config(str(settings.alembic_ini_path))
    config.set_main_option("sqlalchemy.url", render_sync_url(_database_url))
    config.set_main_option("script_location", str(settings.alembic_migrations_dir))
    command.upgrade(config, "head")

    yield

    reset_database_state()
    reload_settings()
    for env_var in (
        "ADE_DATABASE_DSN",
        "ADE_DOCUMENTS_DIR",
        "ADE_CONFIGS_DIR",
        "ADE_VENVS_DIR",
        "ADE_JOBS_DIR",
        "ADE_PIP_CACHE_DIR",
        "ADE_OIDC_ENABLED",
        "ADE_SAFE_MODE",
    ):
        os.environ.pop(env_var, None)


@pytest.fixture(scope="session")
def app(_configure_database: None) -> FastAPI:
    """Return an application instance for integration-style tests."""

    return create_app()


@pytest.fixture()
def override_app_settings(app: FastAPI) -> Callable[..., Settings]:
    """Refresh application settings for a test case."""

    previous_override = app.dependency_overrides.get(get_settings)

    def _apply(**updates: Any) -> Settings:
        base = reload_settings()
        updated = base.model_copy(update=updates)
        app.dependency_overrides[get_settings] = lambda: updated
        app.state.settings = updated
        app.state.safe_mode = bool(updated.safe_mode)
        configure_auth_dependencies(settings=updated)
        ensure_runtime_dirs(updated)
        return updated

    yield _apply

    if previous_override is not None:
        app.dependency_overrides[get_settings] = previous_override
    else:
        app.dependency_overrides.pop(get_settings, None)

    restored = reload_settings()
    app.state.settings = restored
    app.state.safe_mode = bool(restored.safe_mode)
    configure_auth_dependencies(settings=restored)
    ensure_runtime_dirs(restored)


@pytest_asyncio.fixture()
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Provide an HTTPX async client bound to the FastAPI app."""

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


@pytest_asyncio.fixture()
async def seed_identity(app: FastAPI) -> dict[str, Any]:
    """Create baseline users and workspace records for identity tests."""

    settings = get_settings()
    await ensure_database_ready(settings)
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        await sync_permission_registry(session=session)

        workspace_slug = f"acme-{uuid4().hex[:8]}"
        workspace = Workspace(name="Acme Corp", slug=workspace_slug)
        secondary_workspace = Workspace(
            name="Globex Corp", slug=f"{workspace_slug}-alt"
        )
        admin_password = "admin-password"
        workspace_owner_password = "workspace-owner-password"
        member_password = "member-password"
        member_manage_password = "member-manage-password"
        orphan_password = "orphan-password"
        invitee_password = "invitee-password"

        admin_email = f"admin+{workspace_slug}@example.test"
        workspace_owner_email = f"owner+{workspace_slug}@example.test"
        member_email = f"member+{workspace_slug}@example.test"
        member_manage_email = f"member-manage+{workspace_slug}@example.test"
        orphan_email = f"orphan+{workspace_slug}@example.test"
        invitee_email = f"invitee+{workspace_slug}@example.test"

        admin = User(email=admin_email, is_active=True)
        workspace_owner = User(email=workspace_owner_email, is_active=True)
        member = User(email=member_email, is_active=True)
        member_with_manage = User(email=member_manage_email, is_active=True)
        orphan = User(email=orphan_email, is_active=True)
        invitee = User(email=invitee_email, is_active=True)

        session.add_all(
            [
                workspace,
                secondary_workspace,
                admin,
                workspace_owner,
                member,
                member_with_manage,
                orphan,
                invitee,
            ]
        )
        await session.flush()

        global_roles = await session.execute(
            select(Role).where(
                Role.scope_type == "global",
                Role.scope_id.is_(None),
                Role.slug.in_(["global-administrator", "global-user"]),
            )
        )
        global_role_map = {role.slug: role for role in global_roles.scalars()}

        admin_role = global_role_map.get("global-administrator")
        if admin_role is not None:
            await assign_global_role(
                session=session,
                user_id=cast(str, admin.id),
                role_id=cast(str, admin_role.id),
            )

        member_role = global_role_map.get("global-user")
        if member_role is not None:
            for candidate in (
                workspace_owner,
                member,
                member_with_manage,
                orphan,
                invitee,
            ):
                await assign_global_role(
                    session=session,
                    user_id=cast(str, candidate.id),
                    role_id=cast(str, member_role.id),
                )

        def _add_password(user: User, password: str) -> None:
            session.add(
                UserCredential(
                    user_id=user.id,
                    password_hash=hash_password(password),
                    last_rotated_at=datetime.now(tz=UTC),
                )
            )

        for account, secret in (
            (admin, admin_password),
            (workspace_owner, workspace_owner_password),
            (member, member_password),
            (member_with_manage, member_manage_password),
            (orphan, orphan_password),
            (invitee, invitee_password),
        ):
            _add_password(account, secret)

        workspace_owner_membership = WorkspaceMembership(
            user_id=workspace_owner.id,
            workspace_id=workspace.id,
            is_default=True,
        )
        member_membership = WorkspaceMembership(
            user_id=member.id,
            workspace_id=workspace.id,
            is_default=True,
        )
        member_manage_default = WorkspaceMembership(
            user_id=member_with_manage.id,
            workspace_id=workspace.id,
            is_default=True,
        )
        member_manage_secondary = WorkspaceMembership(
            user_id=member_with_manage.id,
            workspace_id=secondary_workspace.id,
            is_default=False,
        )

        session.add_all(
            [
                workspace_owner_membership,
                member_membership,
                member_manage_default,
                member_manage_secondary,
            ]
        )
        await session.flush()

        result = await session.execute(
            select(Role).where(
                Role.scope_type == "workspace",
                Role.scope_id.is_(None),
                Role.slug.in_(["workspace-owner", "workspace-member"]),
            )
        )
        roles = {role.slug: role for role in result.scalars()}

        async def _assign_workspace_role(
            membership: WorkspaceMembership, user: User, slug: str
        ) -> None:
            role = roles.get(slug)
            if role is None:
                return
            principal = await ensure_user_principal(session=session, user=user)
            await assign_role(
                session=session,
                principal_id=principal.id,
                role_id=role.id,
                scope_type="workspace",
                scope_id=membership.workspace_id,
            )

        await _assign_workspace_role(
            workspace_owner_membership, workspace_owner, "workspace-owner"
        )
        await _assign_workspace_role(
            member_membership, member, "workspace-member"
        )
        await _assign_workspace_role(
            member_manage_default, member_with_manage, "workspace-member"
        )
        await _assign_workspace_role(
            member_manage_secondary, member_with_manage, "workspace-member"
        )

        await session.commit()

        workspace_id = workspace.id
        secondary_workspace_id = secondary_workspace.id
        admin_info = {"email": admin_email, "password": admin_password, "id": admin.id}
        workspace_owner_info = {
            "email": workspace_owner_email,
            "password": workspace_owner_password,
            "id": workspace_owner.id,
        }
        member_info = {"email": member_email, "password": member_password, "id": member.id}
        member_manage_info = {
            "email": member_manage_email,
            "password": member_manage_password,
            "id": member_with_manage.id,
        }
        orphan_info = {"email": orphan_email, "password": orphan_password, "id": orphan.id}
        invitee_info = {
            "email": invitee_email,
            "password": invitee_password,
            "id": invitee.id,
        }

    return {
        "workspace_id": workspace_id,
        "secondary_workspace_id": secondary_workspace_id,
        "admin": admin_info,
        "workspace_owner": workspace_owner_info,
        "member": member_info,
        "member_with_manage": member_manage_info,
        "orphan": orphan_info,
        "invitee": invitee_info,
        "user": member_info,
    }
