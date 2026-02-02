"""User management commands."""

from __future__ import annotations

import json
import secrets
import sys
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, Iterator
from uuid import UUID

import typer

if TYPE_CHECKING:
    from ade_db.models import Role, User, UserRoleAssignment
    from ade_api.settings import Settings
    from sqlalchemy.orm import Session


class UserCommandContext:
    """Bundle DB session + services used by the user CLI commands."""

    def __init__(self, *, session: "Session", settings: "Settings") -> None:
        from ade_api.features.rbac.service import RbacService
        from ade_api.features.users.repository import UsersRepository
        from ade_api.features.users.service import UsersService

        self.session = session
        self.settings = settings
        self.repo = UsersRepository(session)
        self.users_service = UsersService(session=session, settings=settings)
        self.rbac = RbacService(session=session)

    def sync_rbac_registry(self) -> None:
        self.rbac.sync_registry()

    def resolve_user(self, ref: str) -> "User":
        """Resolve a user by UUID or email."""

        user = None
        user_id = _coerce_uuid(ref)
        if user_id:
            user = self.repo.get_by_id(user_id)
        if user is None:
            user = self.repo.get_by_email(ref)
        if user is None:
            raise LookupError(f"User not found: {ref}")
        return user

    def resolve_role(self, ref: str) -> "Role":
        """Resolve a role by UUID or slug."""

        role_id = _coerce_uuid(ref)
        role = (
            self.rbac.get_role(role_id)
            if role_id
            else self.rbac.get_role_by_slug(slug=ref)
        )
        if role is None:
            raise LookupError(f"Role not found: {ref}")
        return role


@contextmanager
def _user_context() -> Iterator[UserCommandContext]:
    """Context manager that yields a ``UserCommandContext`` and commits on success."""
    from sqlalchemy.orm import sessionmaker

    from ade_db.engine import build_engine, session_scope
    from ade_api.settings import Settings

    settings = Settings()
    engine = build_engine(settings)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_scope(session_factory) as session:
            yield UserCommandContext(session=session, settings=settings)
    finally:
        engine.dispose()


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


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def _emit_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, default=_json_default))


def _scope_and_workspace(scope: str, workspace_id: str | None):
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


def _workspace_id_for_scope(scope, workspace_id: UUID | None) -> UUID | None:
    scope_value = scope.value if hasattr(scope, "value") else str(scope)
    return workspace_id if scope_value == "workspace" else None


def _assignment_scope(assignment: "UserRoleAssignment") -> tuple[str, UUID | None]:
    workspace_id = assignment.workspace_id
    scope = "workspace" if workspace_id else "global"
    return scope, workspace_id


def _echo_error(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)


def _list_users(
    *,
    include_inactive: bool,
    humans_only: bool,
    query: str | None,
    json_output: bool,
) -> None:
    with _user_context() as ctx:
        users = ctx.repo.list_users()
        rows: list[dict[str, Any]] = []

        def _global_roles(user: "User") -> list[str]:
            roles = ctx.rbac.get_global_role_slugs_for_user(user=user)
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
                    "roles": _global_roles(user),
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
        _emit_json(payload)
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


def _create_user(
    *,
    email: str,
    password: str | None,
    display_name: str | None,
    service_account: bool,
    is_active: bool,
    roles: Iterable[str],
    assign_admin: bool,
    is_superuser: bool,
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

    with _user_context() as ctx:
        existing = ctx.repo.get_by_email(email_clean)
        if existing is not None:
            _echo_error("Email already in use.")
            raise typer.Exit(code=1)

        if password:
            password_hash = hash_password(password)
        else:
            password_hash = hash_password(secrets.token_urlsafe(32))
        try:
            user = ctx.repo.create(
                email=email_clean,
                hashed_password=password_hash,
                display_name=display_name.strip() if display_name else None,
                is_active=is_active,
                is_service_account=service_account,
                is_superuser=is_superuser,
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
                ctx.users_service.update_user(
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
            ctx.sync_rbac_registry()
            for role_ref in desired_roles:
                role = ctx.resolve_role(role_ref)
                assignment = ctx.rbac.assign_role_if_missing(
                    user_id=user.id,
                    role_id=role.id,
                    workspace_id=None,
                )
                assignments.append(assignment)

        profile = ctx.users_service.get_user(user_id=user.id)

    if json_output:
        payload = profile.model_dump()
        payload["assignments"] = [
            {
                "id": str(a.id),
                "role_id": str(a.role_id),
                "role_slug": a.role.slug if a.role else "",
                "scope": _assignment_scope(a)[0],
                "workspace_id": str(a.workspace_id) if a.workspace_id else None,
            }
            for a in assignments
        ]
        _emit_json(payload)
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
            scope, workspace_id = _assignment_scope(assignment)
            typer.echo(
                f"    - {role_slug} ({assignment.role_id}) @ {_scope_label(scope, workspace_id)}"
            )


def _show_user(*, user_ref: str, json_output: bool) -> None:
    from ade_db.models import UserRoleAssignment
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    with _user_context() as ctx:
        user = ctx.resolve_user(user_ref)
        profile = ctx.users_service.get_user(user_id=user.id)

        stmt = (
            select(UserRoleAssignment)
            .options(selectinload(UserRoleAssignment.role))
            .where(UserRoleAssignment.user_id == user.id)
        )
        result = ctx.session.execute(stmt)
        assignments = list(result.scalars().all())

    if json_output:
        payload = profile.model_dump()
        payload["assignments"] = [
            {
                "id": str(a.id),
                "role_id": str(a.role_id),
                "role_slug": a.role.slug if a.role else "",
                "scope": _assignment_scope(a)[0],
                "workspace_id": str(a.workspace_id) if a.workspace_id else None,
                "created_at": _render_datetime(a.created_at),
            }
            for a in assignments
        ]
        _emit_json(payload)
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
            scope, workspace_id = _assignment_scope(assignment)
            typer.echo(
                f"  - {role_slug} ({assignment.role_id}) "
                f"@ {_scope_label(scope, workspace_id)} "
                f"[{assignment.id}]"
            )


def _update_user(
    *,
    user_ref: str,
    display_name: str | None,
    active_flag: bool | None,
    json_output: bool,
) -> None:
    from ade_api.features.users.schemas import UserUpdate
    from fastapi import HTTPException

    payload_data: dict[str, object] = {}
    if display_name is not None:
        payload_data["display_name"] = display_name
    if active_flag is not None:
        payload_data["is_active"] = active_flag

    try:
        payload = UserUpdate(**payload_data)
    except ValueError as exc:
        _echo_error(str(exc))
        raise typer.Exit(code=1) from exc

    with _user_context() as ctx:
        user = ctx.resolve_user(user_ref)
        try:
            updated = ctx.users_service.update_user(
                user_id=user.id,
                payload=payload,
                actor=None,
            )
        except HTTPException as exc:
            _echo_error(str(exc.detail))
            raise typer.Exit(code=1) from exc

    if json_output:
        _emit_json(updated.model_dump())
        return

    typer.echo(f"Updated user {updated.email} ({updated.id})")
    typer.echo(f"  active: {updated.is_active}")
    typer.echo(f"  name:   {updated.display_name or '-'}")


def _set_password(*, user_ref: str, password: str) -> None:
    from ade_api.core.security.hashing import hash_password

    with _user_context() as ctx:
        user = ctx.resolve_user(user_ref)
        password_hash = hash_password(password)
        ctx.repo.set_password(user, password_hash)
        label = user.email or str(user.id)
    typer.echo(f"Rotated password for {label}")


def _delete_user(*, user_ref: str, yes: bool) -> None:
    with _user_context() as ctx:
        user = ctx.resolve_user(user_ref)
        label = user.email or str(user.id)
        if not yes:
            confirmed = typer.confirm(
                f"Delete user {label} ({user.id})? This removes credentials and assignments.",
                default=False,
            )
            if not confirmed:
                typer.echo("Deletion cancelled.")
                return
        ctx.session.delete(user)
        ctx.session.flush()
    typer.echo(f"Deleted user {label}")


def _list_roles(
    *,
    user_ref: str,
    scope: str,
    workspace_id: str | None,
    limit: int,
    json_output: bool,
) -> None:
    from ade_api.common.list_filters import FilterItem, FilterJoinOperator, FilterOperator
    from ade_api.common.cursor_listing import resolve_cursor_sort
    from ade_api.features.rbac.sorting import (
        ASSIGNMENT_DEFAULT_SORT,
        ASSIGNMENT_CURSOR_FIELDS,
        ASSIGNMENT_ID_FIELD,
        ASSIGNMENT_SORT_FIELDS,
    )

    try:
        scope_value, workspace_uuid = _scope_and_workspace(scope, workspace_id)
    except ValueError as exc:
        _echo_error(str(exc))
        raise typer.Exit(code=1) from exc

    with _user_context() as ctx:
        user = ctx.resolve_user(user_ref)
        user_label = user.email or str(user.id)
        workspace_filter = _workspace_id_for_scope(scope_value, workspace_uuid)
        filters = [
            FilterItem(id="userId", operator=FilterOperator.EQ, value=str(user.id)),
            FilterItem(
                id="scopeId",
                operator=(
                    FilterOperator.IS_EMPTY
                    if workspace_filter is None
                    else FilterOperator.EQ
                ),
                value=None if workspace_filter is None else str(workspace_filter),
            ),
        ]
        resolved_sort = resolve_cursor_sort(
            [],
            allowed=ASSIGNMENT_SORT_FIELDS,
            cursor_fields=ASSIGNMENT_CURSOR_FIELDS,
            default=ASSIGNMENT_DEFAULT_SORT,
            id_field=ASSIGNMENT_ID_FIELD,
        )
        page = ctx.rbac.list_assignments(
            filters=filters,
            join_operator=FilterJoinOperator.AND,
            q=None,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=None,
            include_total=False,
            default_active_only=False,
        )
        assignments = list(page.items)

    if json_output:
        payload = [
            {
                "id": str(a.id),
                "role_id": str(a.role_id),
                "role_slug": a.role.slug if a.role else "",
                "scope": _assignment_scope(a)[0],
                "workspace_id": str(a.workspace_id) if a.workspace_id else None,
                "created_at": _render_datetime(a.created_at),
            }
            for a in assignments
        ]
        _emit_json(payload)
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


def _assign_role(
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

    with _user_context() as ctx:
        ctx.sync_rbac_registry()
        user = ctx.resolve_user(user_ref)
        role = ctx.resolve_role(role_ref)
        user_label = user.email or str(user.id)
        role_label = role.slug
        workspace_target = _workspace_id_for_scope(scope_value, workspace_uuid)
        try:
            if if_missing:
                assignment = ctx.rbac.assign_role_if_missing(
                    user_id=user.id,
                    role_id=role.id,
                    workspace_id=workspace_target,
                )
            else:
                assignment = ctx.rbac.assign_role(
                    user_id=user.id,
                    role_id=role.id,
                    workspace_id=workspace_target,
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


def _remove_role(
    *,
    user_ref: str | None,
    role_ref: str | None,
        assignment_id: str | None,
        scope: str,
        workspace_id: str | None,
    ) -> None:
    from ade_api.features.rbac.service import AssignmentNotFoundError, ScopeMismatchError

    with _user_context() as ctx:
        if assignment_id:
            assignment_uuid = _coerce_uuid(assignment_id)
            if assignment_uuid is None:
                _echo_error("assignment-id must be a valid UUID.")
                raise typer.Exit(code=1)
            assignment = ctx.rbac.get_assignment(assignment_id=assignment_uuid)
            if assignment is None:
                _echo_error("Role assignment not found.")
                raise typer.Exit(code=1)
            scope_value, workspace_uuid = _assignment_scope(assignment)
        else:
            if not user_ref or not role_ref:
                _echo_error("Provide --assignment-id or both --user and --role.")
                raise typer.Exit(code=1)
            try:
                scope_value, workspace_uuid = _scope_and_workspace(scope, workspace_id)
            except ValueError as exc:
                _echo_error(str(exc))
                raise typer.Exit(code=1) from exc
            workspace_uuid = _workspace_id_for_scope(scope_value, workspace_uuid)
            user = ctx.resolve_user(user_ref)
            role = ctx.resolve_role(role_ref)
            assignment = ctx.rbac.get_assignment_for_user_role(
                user_id=user.id,
                role_id=role.id,
                workspace_id=workspace_uuid,
            )
            if assignment is None:
                _echo_error("No matching assignment found.")
                raise typer.Exit(code=1)
        assignment_id = str(assignment.id)
        try:
            ctx.rbac.delete_assignment(
                assignment_id=assignment.id,
                workspace_id=workspace_uuid,
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
        _list_users(
            include_inactive=include_inactive,
            humans_only=humans_only,
            query=query,
            json_output=json_output,
        )

    @users_app.command("show", help="Show a single user by ID or email.")
    def show_user(
        user: str = typer.Argument(..., help="User UUID or email address."),
        json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        _show_user(user_ref=user, json_output=json_output)

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
        superuser: bool = typer.Option(
            False,
            "--superuser",
            help="Create as a superuser (bypasses RBAC checks).",
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

        _create_user(
            email=email,
            password=password,
            display_name=display_name,
            service_account=service_account,
            is_active=not inactive,
            roles=roles,
            assign_admin=admin or superuser,
            is_superuser=superuser,
            json_output=json_output,
        )

    @users_app.command(
        "create-admin",
        help="Create a superuser account (alias for users create --superuser).",
    )
    def create_admin(
        email: str = typer.Argument(..., help="Email for the new administrator."),
        display_name: str | None = typer.Option(
            None,
            "--display-name",
            "--name",
            help="Optional display name.",
        ),
        password: str | None = typer.Option(
            None,
            "--password",
            help="Initial password. If omitted, you will be prompted.",
        ),
        json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        create_user(
            email=email,
            display_name=display_name,
            password=password,
            no_password=False,
            service_account=False,
            inactive=False,
            admin=True,
            superuser=True,
            roles=[],
            json_output=json_output,
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
        _update_user(
            user_ref=user,
            display_name=display_name,
            active_flag=active,
            json_output=json_output,
        )

    @users_app.command("activate", help="Activate a user account.")
    def activate(
        user: str = typer.Argument(..., help="User UUID or email address."),
    ) -> None:
        _update_user(
            user_ref=user,
            display_name=None,
            active_flag=True,
            json_output=False,
        )

    @users_app.command("deactivate", help="Deactivate a user account and revoke access.")
    def deactivate(
        user: str = typer.Argument(..., help="User UUID or email address."),
    ) -> None:
        _update_user(
            user_ref=user,
            display_name=None,
            active_flag=False,
            json_output=False,
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
        _set_password(user_ref=user, password=chosen)

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
        _delete_user(user_ref=user, yes=yes)

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
        _list_roles(
            user_ref=user,
            scope=scope,
            workspace_id=workspace_id,
            limit=limit,
            json_output=json_output,
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
        _assign_role(
            user_ref=user,
            role_ref=role,
            scope=scope,
            workspace_id=workspace_id,
            if_missing=if_missing,
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
        _remove_role(
            user_ref=user,
            role_ref=role,
            assignment_id=assignment_id,
            scope=scope,
            workspace_id=workspace_id,
        )

    app.add_typer(users_app, name="users")
