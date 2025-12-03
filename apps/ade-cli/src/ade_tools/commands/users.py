"""User management commands."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterable
from uuid import UUID

import typer

from ade_tools.commands import common

if TYPE_CHECKING:
    from ade_api.core.models import Role, User, UserRoleAssignment
    from ade_api.settings import Settings
    from sqlalchemy.ext.asyncio import AsyncSession


class UserCommandContext:
    """Bundle DB session + services used by the user CLI commands."""

    def __init__(self, *, session: "AsyncSession", settings: "Settings") -> None:
        from ade_api.features.rbac.service import RbacService
        from ade_api.features.users.repository import UsersRepository
        from ade_api.features.users.service import UsersService

        self.session = session
        self.settings = settings
        self.repo = UsersRepository(session)
        self.users_service = UsersService(session=session, settings=settings)
        self.rbac = RbacService(session=session)

    async def sync_rbac_registry(self) -> None:
        await self.rbac.sync_registry()

    async def resolve_user(self, ref: str) -> "User":
        """Resolve a user by UUID or email."""

        user = None
        user_id = _coerce_uuid(ref)
        if user_id:
            user = await self.repo.get_by_id(user_id)
        if user is None:
            user = await self.repo.get_by_email(ref)
        if user is None:
            raise LookupError(f"User not found: {ref}")
        return user

    async def resolve_role(self, ref: str) -> "Role":
        """Resolve a role by UUID or slug."""

        role_id = _coerce_uuid(ref)
        role = (
            await self.rbac.get_role(role_id)
            if role_id
            else await self.rbac.get_role_by_slug(slug=ref)
        )
        if role is None:
            raise LookupError(f"Role not found: {ref}")
        return role


def _ensure_backend() -> None:
    """Fail fast if ADE backend dependencies are missing."""

    common.refresh_paths()
    common.ensure_backend_dir()
    common.require_python_module(
        "ade_api",
        "Install ADE into your virtualenv (e.g., `pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`).",
    )


@asynccontextmanager
async def _user_context() -> AsyncIterator[UserCommandContext]:
    """Async context manager that yields a ``UserCommandContext`` and commits on success."""

    _ensure_backend()
    from ade_api.infra.db import get_sessionmaker
    from ade_api.settings import Settings

    settings = Settings()
    session_factory = get_sessionmaker(settings=settings)
    session = session_factory()
    ctx = UserCommandContext(session=session, settings=settings)
    try:
        yield ctx
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def _coerce_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _render_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat()


def _scope_and_workspace(scope: str, workspace_id: str | None):
    _ensure_backend()
    from ade_api.core.rbac.types import ScopeType

    normalized = scope.lower().strip()
    try:
        scope_type = ScopeType(normalized)
    except ValueError as exc:
        raise ValueError("Scope must be 'global' or 'workspace'.") from exc

    if scope_type.value == "workspace":
        workspace_uuid = _coerce_uuid(workspace_id)
        if workspace_uuid is None:
            raise ValueError("Workspace scope requires --workspace-id.")
        return scope_type, workspace_uuid

    if workspace_id:
        raise ValueError("--workspace-id is only valid with --scope workspace.")
    return scope_type, None


def _scope_label(scope, workspace_id: UUID | None) -> str:
    scope_value = scope.value if hasattr(scope, "value") else str(scope)
    if scope_value == "workspace":
        return f"workspace:{workspace_id}"
    return "global"


def _echo_error(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)


async def _list_users(
    *,
    include_inactive: bool,
    humans_only: bool,
    query: str | None,
    json_output: bool,
) -> None:
    async with _user_context() as ctx:
        users = await ctx.repo.list_users()
        rows: list[dict[str, Any]] = []

        async def _global_roles(user: "User") -> list[str]:
            roles = await ctx.rbac.get_global_role_slugs_for_user(user=user)
            return sorted(roles)

        for user in users:
            if not include_inactive and not user.is_active:
                continue
            if humans_only and user.is_service_account:
                continue
            if query:
                haystack = f"{user.email} {user.display_name or ''}".lower()
                if query.lower() not in haystack:
                    continue
            rows.append(
                {
                    "id": str(user.id),
                    "email": user.email,
                    "display_name": user.display_name,
                    "is_active": user.is_active,
                    "is_service_account": user.is_service_account,
                    "roles": await _global_roles(user),
                }
            )

    if json_output:
        payload = [
            {
                "id": row["id"],
                "email": row["email"],
                "display_name": row["display_name"],
                "is_active": row["is_active"],
                "is_service_account": row["is_service_account"],
                "roles": row["roles"],
            }
            for row in rows
        ]
        typer.echo(json.dumps(payload, indent=2))
        return

    if not rows:
        typer.echo("No users found.")
        return

    header = f"{'ID':36}  {'Email':30}  Active  Service  Roles"
    typer.echo(header)
    typer.echo("-" * len(header))
    for row in rows:
        roles = ", ".join(row["roles"]) or "-"
        typer.echo(
            f"{row['id']:36}  {row['email']:30}  "
            f"{'yes' if row['is_active'] else 'no ':<6}  "
            f"{'yes' if row['is_service_account'] else 'no ':<7}  {roles}"
        )


async def _create_user(
    *,
    email: str,
    password: str | None,
    display_name: str | None,
    service_account: bool,
    is_active: bool,
    roles: Iterable[str],
    assign_admin: bool,
    json_output: bool,
) -> None:
    from ade_api.core.security.hashing import hash_password
    from ade_api.features.users.schemas import UserUpdate
    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError

    email_clean = email.strip()
    if not email_clean:
        _echo_error("Email is required.")
        raise typer.Exit(code=1)

    async with _user_context() as ctx:
        existing = await ctx.repo.get_by_email(email_clean)
        if existing is not None:
            _echo_error("Email already in use.")
            raise typer.Exit(code=1)

        password_hash = hash_password(password) if password else None
        try:
            user = await ctx.repo.create(
                email=email_clean,
                password_hash=password_hash,
                display_name=display_name.strip() if display_name else None,
                is_active=is_active,
                is_service_account=service_account,
            )
        except ValueError as exc:
            _echo_error(str(exc))
            raise typer.Exit(code=1) from exc
        except IntegrityError as exc:
            _echo_error("Failed to create user due to a database constraint.")
            raise typer.Exit(code=1) from exc

        # Align inactive creation with standard deactivation flow.
        if not is_active:
            payload = UserUpdate(is_active=False)
            try:
                await ctx.users_service.update_user(
                    user_id=user.id,
                    payload=payload,
                    actor=None,
                )
            except HTTPException as exc:
                _echo_error(str(exc.detail))
                raise typer.Exit(code=1) from exc

        assignments: list[UserRoleAssignment] = []

        desired_roles = []
        if assign_admin:
            desired_roles.append("global-admin")
        desired_roles.extend(roles)
        desired_roles = list(dict.fromkeys(desired_roles))

        if desired_roles:
            await ctx.sync_rbac_registry()
            for role_ref in desired_roles:
                role = await ctx.resolve_role(role_ref)
                assignment = await ctx.rbac.assign_role_if_missing(
                    user_id=user.id,
                    role_id=role.id,
                    scope_type="global",
                    scope_id=None,
                )
                assignments.append(assignment)

        profile = await ctx.users_service.get_user(user_id=user.id)

    if json_output:
        payload = profile.model_dump()
        payload["assignments"] = [
            {
                "id": str(a.id),
                "role_id": str(a.role_id),
                "role_slug": a.role.slug if a.role else "",
                "scope_type": a.scope_type,
                "scope_id": str(a.scope_id) if a.scope_id else None,
            }
            for a in assignments
        ]
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"Created user {profile.email} ({profile.id})")
    typer.echo(f"  active: {profile.is_active}")
    typer.echo(f"  service account: {profile.is_service_account}")
    if profile.display_name:
        typer.echo(f"  name: {profile.display_name}")
    if assignments:
        typer.echo("  roles:")
        for assignment in assignments:
            role_slug = assignment.role.slug if assignment.role else ""
            typer.echo(f"    - {role_slug} ({assignment.role_id}) @ {_scope_label(assignment.scope_type, assignment.scope_id)}")


async def _show_user(*, user_ref: str, json_output: bool) -> None:
    from ade_api.core.models.rbac import UserRoleAssignment
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async with _user_context() as ctx:
        user = await ctx.resolve_user(user_ref)
        profile = await ctx.users_service.get_user(user_id=user.id)

        stmt = (
            select(UserRoleAssignment)
            .options(selectinload(UserRoleAssignment.role))
            .where(UserRoleAssignment.user_id == user.id)
        )
        result = await ctx.session.execute(stmt)
        assignments = list(result.scalars().all())

    if json_output:
        payload = profile.model_dump()
        payload["assignments"] = [
            {
                "id": str(a.id),
                "role_id": str(a.role_id),
                "role_slug": a.role.slug if a.role else "",
                "scope_type": a.scope_type,
                "scope_id": str(a.scope_id) if a.scope_id else None,
                "created_at": _render_datetime(a.created_at),
            }
            for a in assignments
        ]
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"ID:           {profile.id}")
    typer.echo(f"Email:        {profile.email}")
    typer.echo(f"Active:       {profile.is_active}")
    typer.echo(f"Service acct: {profile.is_service_account}")
    typer.echo(f"Name:         {profile.display_name or '-'}")
    typer.echo(f"Created:      {_render_datetime(profile.created_at)}")
    typer.echo(f"Updated:      {_render_datetime(profile.updated_at)}")
    typer.echo(f"Global roles: {', '.join(profile.roles) or '-'}")
    if assignments:
        typer.echo("Assignments:")
        for assignment in assignments:
            role_slug = assignment.role.slug if assignment.role else ""
            typer.echo(
                f"  - {role_slug} ({assignment.role_id}) "
                f"@ {_scope_label(assignment.scope_type, assignment.scope_id)} "
                f"[{assignment.id}]"
            )


async def _update_user(
    *,
    user_ref: str,
    display_name: str | None,
    active_flag: bool | None,
    json_output: bool,
) -> None:
    from ade_api.features.users.schemas import UserUpdate
    from fastapi import HTTPException

    try:
        payload = UserUpdate(
            display_name=display_name,
            is_active=active_flag,
        )
    except ValueError as exc:
        _echo_error(str(exc))
        raise typer.Exit(code=1) from exc

    async with _user_context() as ctx:
        user = await ctx.resolve_user(user_ref)
        try:
            updated = await ctx.users_service.update_user(
                user_id=user.id,
                payload=payload,
                actor=None,
            )
        except HTTPException as exc:
            _echo_error(str(exc.detail))
            raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(updated.model_dump(), indent=2))
        return

    typer.echo(f"Updated user {updated.email} ({updated.id})")
    typer.echo(f"  active: {updated.is_active}")
    typer.echo(f"  name:   {updated.display_name or '-'}")


async def _set_password(*, user_ref: str, password: str) -> None:
    from ade_api.core.security.hashing import hash_password

    async with _user_context() as ctx:
        user = await ctx.resolve_user(user_ref)
        password_hash = hash_password(password)
        await ctx.repo.set_password(user, password_hash)
        label = user.email or str(user.id)
    typer.echo(f"Rotated password for {label}")


async def _delete_user(*, user_ref: str, yes: bool) -> None:
    async with _user_context() as ctx:
        user = await ctx.resolve_user(user_ref)
        label = user.email or str(user.id)
        if not yes:
            confirmed = typer.confirm(
                f"Delete user {label} ({user.id})? This removes credentials and assignments.",
                default=False,
            )
            if not confirmed:
                typer.echo("Deletion cancelled.")
                return
        await ctx.session.delete(user)
        await ctx.session.flush()
    typer.echo(f"Deleted user {label}")


async def _list_roles(
    *,
    user_ref: str,
    scope: str,
    workspace_id: str | None,
    limit: int,
    json_output: bool,
) -> None:
    try:
        scope_value, workspace_uuid = _scope_and_workspace(scope, workspace_id)
    except ValueError as exc:
        _echo_error(str(exc))
        raise typer.Exit(code=1) from exc

    async with _user_context() as ctx:
        user = await ctx.resolve_user(user_ref)
        user_label = user.email or str(user.id)
        page = await ctx.rbac.list_assignments(
            scope_type=scope_value,
            scope_id=workspace_uuid,
            user_id=user.id,
            role_id=None,
            page=1,
            page_size=limit,
            include_total=False,
            include_inactive=True,
        )
        assignments = list(page.items)

    if json_output:
        payload = [
            {
                "id": str(a.id),
                "role_id": str(a.role_id),
                "role_slug": a.role.slug if a.role else "",
                "scope_type": a.scope_type,
                "scope_id": str(a.scope_id) if a.scope_id else None,
                "created_at": _render_datetime(a.created_at),
            }
            for a in assignments
        ]
        typer.echo(json.dumps(payload, indent=2))
        return

    if not assignments:
        typer.echo("No role assignments found.")
        return

    typer.echo(f"Assignments for {user_label} ({_scope_label(scope_value, workspace_uuid)}):")
    for assignment in assignments:
        role_slug = assignment.role.slug if assignment.role else ""
        typer.echo(
            f"  - {role_slug} ({assignment.role_id}) "
            f"[{assignment.id}] created {_render_datetime(assignment.created_at)}"
        )


async def _assign_role(
    *,
    user_ref: str,
    role_ref: str,
        scope: str,
        workspace_id: str | None,
        if_missing: bool,
    ) -> None:
    from ade_api.features.rbac.service import AssignmentError, RoleConflictError, ScopeMismatchError

    try:
        scope_value, workspace_uuid = _scope_and_workspace(scope, workspace_id)
    except ValueError as exc:
        _echo_error(str(exc))
        raise typer.Exit(code=1) from exc

    async with _user_context() as ctx:
        await ctx.sync_rbac_registry()
        user = await ctx.resolve_user(user_ref)
        role = await ctx.resolve_role(role_ref)
        user_label = user.email or str(user.id)
        role_label = role.slug
        try:
            if if_missing:
                assignment = await ctx.rbac.assign_role_if_missing(
                    user_id=user.id,
                    role_id=role.id,
                    scope_type=scope_value,
                    scope_id=workspace_uuid,
                )
            else:
                assignment = await ctx.rbac.assign_role(
                    user_id=user.id,
                    role_id=role.id,
                    scope_type=scope_value,
                    scope_id=workspace_uuid,
                )
        except (AssignmentError, RoleConflictError, ScopeMismatchError) as exc:
            _echo_error(str(exc))
            raise typer.Exit(code=1) from exc
        assignment_id = str(assignment.id)

    typer.echo(
        f"Assigned {role_label} to {user_label} "
        f"@ {_scope_label(scope_value, workspace_uuid)} "
        f"(assignment {assignment_id})"
    )


async def _remove_role(
    *,
    user_ref: str | None,
    role_ref: str | None,
        assignment_id: str | None,
        scope: str,
        workspace_id: str | None,
    ) -> None:
    from ade_api.features.rbac.service import AssignmentNotFoundError, ScopeMismatchError

    async with _user_context() as ctx:
        if assignment_id:
            assignment_uuid = _coerce_uuid(assignment_id)
            if assignment_uuid is None:
                _echo_error("assignment-id must be a valid UUID.")
                raise typer.Exit(code=1)
            assignment = await ctx.rbac.get_assignment(assignment_id=assignment_uuid)
            if assignment is None:
                _echo_error("Role assignment not found.")
                raise typer.Exit(code=1)
            scope_value = assignment.scope_type
            workspace_uuid = assignment.scope_id
        else:
            if not user_ref or not role_ref:
                _echo_error("Provide --assignment-id or both --user and --role.")
                raise typer.Exit(code=1)
            try:
                scope_value, workspace_uuid = _scope_and_workspace(scope, workspace_id)
            except ValueError as exc:
                _echo_error(str(exc))
                raise typer.Exit(code=1) from exc
            user = await ctx.resolve_user(user_ref)
            role = await ctx.resolve_role(role_ref)
            assignment = await ctx.rbac.get_assignment_for_user_role(
                user_id=user.id,
                role_id=role.id,
                scope_type=scope_value,
                scope_id=workspace_uuid,
            )
            if assignment is None:
                _echo_error("No matching assignment found.")
                raise typer.Exit(code=1)
        assignment_id = str(assignment.id)
        try:
            await ctx.rbac.delete_assignment(
                assignment_id=assignment.id,
                scope_type=scope_value,
                scope_id=workspace_uuid,
            )
        except (AssignmentNotFoundError, ScopeMismatchError) as exc:
            _echo_error(str(exc))
            raise typer.Exit(code=1) from exc

    typer.echo(
        f"Removed assignment {assignment_id} "
        f"({_scope_label(scope_value, workspace_uuid)})"
    )


def register(app: typer.Typer) -> None:
    users_app = typer.Typer(help="Manage ADE users and their role assignments.")
    roles_app = typer.Typer(help="Manage role assignments for a user.")
    users_app.add_typer(roles_app, name="roles")

    @users_app.command("list", help="List users (active humans by default).")
    def list_users(
        include_inactive: bool = typer.Option(
            False,
            "--include-inactive",
            help="Include deactivated users.",
        ),
        humans_only: bool = typer.Option(
            False,
            "--humans-only",
            help="Exclude service accounts.",
        ),
        query: str | None = typer.Option(
            None,
            "--query",
            "-q",
            help="Case-insensitive substring filter on email/display name.",
        ),
        json_output: bool = typer.Option(
            False,
            "--json",
            help="Emit JSON instead of a table.",
        ),
    ) -> None:
        asyncio.run(
            _list_users(
                include_inactive=include_inactive,
                humans_only=humans_only,
                query=query,
                json_output=json_output,
            )
        )

    @users_app.command("show", help="Show a single user by ID or email.")
    def show_user(
        user: str = typer.Argument(..., help="User UUID or email address."),
        json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        asyncio.run(_show_user(user_ref=user, json_output=json_output))

    @users_app.command("create", help="Create a user and optionally assign global roles.")
    def create_user(
        email: str = typer.Argument(..., help="Email for the new user."),
        display_name: str | None = typer.Option(
            None,
            "--display-name",
            "--name",
            help="Optional display name.",
        ),
        password: str | None = typer.Option(
            None,
            "--password",
            help="Initial password. If omitted, you will be prompted unless --no-password is used.",
        ),
        no_password: bool = typer.Option(
            False,
            "--no-password",
            help="Skip password creation (service accounts only).",
        ),
        service_account: bool = typer.Option(
            False,
            "--service-account",
            help="Create as a service account.",
        ),
        inactive: bool = typer.Option(
            False,
            "--inactive",
            help="Create the user in a deactivated state.",
        ),
        admin: bool = typer.Option(
            False,
            "--admin",
            help="Assign the built-in global-admin role.",
        ),
        roles: list[str] = typer.Option(
            [],
            "--role",
            help="Assign additional global role slugs or IDs.",
        ),
        json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        if no_password and not service_account:
            _echo_error("Use --no-password only for service accounts.")
            raise typer.Exit(code=1)

        if password is None and not no_password:
            if not sys.stdin.isatty():
                _echo_error("Password is required; pass --password or --no-password.")
                raise typer.Exit(code=1)
            password = typer.prompt(
                "Password",
                hide_input=True,
                confirmation_prompt=True,
            )
        if password is not None and not password.strip():
            _echo_error("Password cannot be empty.")
            raise typer.Exit(code=1)

        asyncio.run(
            _create_user(
                email=email,
                password=password,
                display_name=display_name,
                service_account=service_account,
                is_active=not inactive,
                roles=roles,
                assign_admin=admin,
                json_output=json_output,
            )
        )

    @users_app.command("update", help="Update display name or activation state for a user.")
    def update_user(
        user: str = typer.Argument(..., help="User UUID or email address."),
        display_name: str | None = typer.Option(
            None,
            "--display-name",
            "--name",
            help="New display name (use empty string to clear).",
        ),
        active: bool | None = typer.Option(
            None,
            "--active/--inactive",
            help="Set activation state.",
        ),
        json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        asyncio.run(
            _update_user(
                user_ref=user,
                display_name=display_name,
                active_flag=active,
                json_output=json_output,
            )
        )

    @users_app.command("activate", help="Activate a user account.")
    def activate(
        user: str = typer.Argument(..., help="User UUID or email address."),
    ) -> None:
        asyncio.run(
            _update_user(
                user_ref=user,
                display_name=None,
                active_flag=True,
                json_output=False,
            )
        )

    @users_app.command("deactivate", help="Deactivate a user account and revoke access.")
    def deactivate(
        user: str = typer.Argument(..., help="User UUID or email address."),
    ) -> None:
        asyncio.run(
            _update_user(
                user_ref=user,
                display_name=None,
                active_flag=False,
                json_output=False,
            )
        )

    @users_app.command("set-password", help="Rotate a user's password.")
    def set_password(
        user: str = typer.Argument(..., help="User UUID or email address."),
        password: str | None = typer.Option(
            None,
            "--password",
            help="New password (prompted if omitted).",
        ),
    ) -> None:
        chosen = password
        if chosen is None:
            if not sys.stdin.isatty():
                _echo_error("Password is required; pass --password when non-interactive.")
                raise typer.Exit(code=1)
            chosen = typer.prompt(
                "New password",
                hide_input=True,
                confirmation_prompt=True,
            )
        if not chosen.strip():
            _echo_error("Password cannot be empty.")
            raise typer.Exit(code=1)
        asyncio.run(_set_password(user_ref=user, password=chosen))

    @users_app.command("delete", help="Delete a user and all related credentials/assignments.")
    def delete_user(
        user: str = typer.Argument(..., help="User UUID or email address."),
        yes: bool = typer.Option(
            False,
            "--yes",
            "-y",
            help="Skip confirmation prompts.",
        ),
    ) -> None:
        asyncio.run(_delete_user(user_ref=user, yes=yes))

    @roles_app.command("list", help="List role assignments for a user.")
    def list_roles(
        user: str = typer.Argument(..., help="User UUID or email address."),
        scope: str = typer.Option(
            "global",
            "--scope",
            help="Scope for the lookup: global or workspace.",
        ),
        workspace_id: str | None = typer.Option(
            None,
            "--workspace-id",
            help="Workspace ID (required when --scope workspace).",
        ),
        limit: int = typer.Option(
            100,
            "--limit",
            min=1,
            help="Maximum assignments to return.",
        ),
        json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        asyncio.run(
            _list_roles(
                user_ref=user,
                scope=scope,
                workspace_id=workspace_id,
                limit=limit,
                json_output=json_output,
            )
        )

    @roles_app.command("assign", help="Assign a role to a user.")
    def assign_role(
        user: str = typer.Argument(..., help="User UUID or email address."),
        role: str = typer.Argument(..., help="Role slug or UUID to assign."),
        scope: str = typer.Option(
            "global",
            "--scope",
            help="Scope for the assignment: global or workspace.",
        ),
        workspace_id: str | None = typer.Option(
            None,
            "--workspace-id",
            help="Workspace ID (required when --scope workspace).",
        ),
        if_missing: bool = typer.Option(
            True,
            "--if-missing/--require-new",
            help="Skip duplicates when already assigned.",
        ),
    ) -> None:
        asyncio.run(
            _assign_role(
                user_ref=user,
                role_ref=role,
                scope=scope,
                workspace_id=workspace_id,
                if_missing=if_missing,
            )
        )

    @roles_app.command("remove", help="Remove a role assignment.")
    def remove_role(
        assignment_id: str | None = typer.Option(
            None,
            "--assignment-id",
            help="Assignment UUID to remove.",
        ),
        user: str | None = typer.Option(
            None,
            "--user",
            help="User UUID or email (required when not using --assignment-id).",
        ),
        role: str | None = typer.Option(
            None,
            "--role",
            help="Role slug or UUID (required when not using --assignment-id).",
        ),
        scope: str = typer.Option(
            "global",
            "--scope",
            help="Scope for the assignment when removing by role.",
        ),
        workspace_id: str | None = typer.Option(
            None,
            "--workspace-id",
            help="Workspace ID (required for workspace scope).",
        ),
    ) -> None:
        asyncio.run(
            _remove_role(
                user_ref=user,
                role_ref=role,
                assignment_id=assignment_id,
                scope=scope,
                workspace_id=workspace_id,
            )
        )

    app.add_typer(users_app, name="users")
