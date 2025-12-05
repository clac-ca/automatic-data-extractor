"""Shared pytest fixtures for backend tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from ade_api.core.models import Role, User, UserCredential, Workspace, WorkspaceMembership
from ade_api.core.rbac.types import ScopeType
from ade_api.core.security.hashing import hash_password
from ade_api.features.rbac.service import RbacService
from ade_api.main import create_app
from ade_api.settings import Settings, get_settings, reload_settings
from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.infra.db.engine import ensure_database_ready, render_sync_url, reset_database_state
from ade_api.infra.db.session import get_sessionmaker


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
    workspaces_dir = data_dir / "workspaces"
    templates_dir = data_dir / "templates" / "config_packages"
    venvs_dir = data_dir / "venvs"
    pip_cache_dir = data_dir / "cache" / "pip"

    os.environ["ADE_DATABASE_DSN"] = _database_url
    os.environ["ADE_WORKSPACES_DIR"] = str(workspaces_dir)
    os.environ["ADE_DOCUMENTS_DIR"] = str(workspaces_dir)
    os.environ["ADE_CONFIGS_DIR"] = str(workspaces_dir)
    os.environ["ADE_CONFIG_TEMPLATES_DIR"] = str(templates_dir)
    os.environ["ADE_VENVS_DIR"] = str(venvs_dir)
    os.environ["ADE_RUNS_DIR"] = str(workspaces_dir)
    os.environ["ADE_PIP_CACHE_DIR"] = str(pip_cache_dir)
    os.environ["ADE_AUTH_DISABLED"] = "false"
    # Speed up test password hashing (hash values remain self-describing via parameters).
    os.environ["ADE_TEST_FAST_HASH"] = "1"
    os.environ.setdefault("ADE_JWT_SECRET", "test-jwt-secret-for-tests-please-change")
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
    assert settings.auth_disabled is False
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
        "ADE_WORKSPACES_DIR",
        "ADE_DOCUMENTS_DIR",
        "ADE_CONFIGS_DIR",
        "ADE_CONFIG_TEMPLATES_DIR",
        "ADE_CONFIG_TEMPLATES_SOURCE_DIR",
        "ADE_VENVS_DIR",
        "ADE_RUNS_DIR",
        "ADE_PIP_CACHE_DIR",
        "ADE_OIDC_ENABLED",
        "ADE_SAFE_MODE",
        "ADE_JWT_SECRET",
        "ADE_AUTH_DISABLED",
        "ADE_TEST_FAST_HASH",
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
        rbac_service = RbacService(session=session)
        await rbac_service.sync_registry()

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

        admin_email = f"admin+{workspace_slug}@example.com"
        workspace_owner_email = f"owner+{workspace_slug}@example.com"
        member_email = f"member+{workspace_slug}@example.com"
        member_manage_email = f"member-manage+{workspace_slug}@example.com"
        orphan_email = f"orphan+{workspace_slug}@example.com"
        invitee_email = f"invitee+{workspace_slug}@example.com"

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

        admin_role = await rbac_service.get_role_by_slug(slug="global-admin")
        if admin_role is not None:
            await rbac_service.assign_role_if_missing(
                user_id=cast(UUID, admin.id),
                role_id=admin_role.id,
                scope_type=ScopeType.GLOBAL,
                scope_id=None,
            )

        member_role = await rbac_service.get_role_by_slug(slug="global-user")
        if member_role is not None:
            for candidate in (
                workspace_owner,
                member,
                member_with_manage,
                orphan,
                invitee,
            ):
                await rbac_service.assign_role_if_missing(
                    user_id=cast(UUID, candidate.id),
                    role_id=member_role.id,
                    scope_type=ScopeType.GLOBAL,
                    scope_id=None,
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

        workspace_roles: dict[str, Role] = {}
        for slug in ("workspace-owner", "workspace-member"):
            role = await rbac_service.get_role_by_slug(slug=slug)
            if role is not None:
                workspace_roles[slug] = role

        async def _assign_workspace_role(
            membership: WorkspaceMembership, user: User, slug: str
        ) -> None:
            role = workspace_roles.get(slug)
            if role is None:
                return
            await rbac_service.assign_role_if_missing(
                user_id=cast(UUID, user.id),
                role_id=role.id,
                scope_type=ScopeType.WORKSPACE,
                scope_id=cast(UUID, membership.workspace_id),
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
        owner_role = workspace_roles.get("workspace-owner")
        if owner_role is not None:
            await rbac_service.assign_role_if_missing(
                user_id=cast(UUID, admin.id),
                role_id=owner_role.id,
                scope_type=ScopeType.WORKSPACE,
                scope_id=cast(UUID, workspace.id),
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
