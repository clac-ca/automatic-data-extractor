from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.core.security.hashing import hash_password
from ade_api.features.rbac.service import RbacService
from ade_db.models import (
    AssignmentScopeType,
    Group,
    GroupMembership,
    PrincipalType,
    Role,
    User,
    UserRoleAssignment,
    WorkspaceMembership,
)


def role_id_by_slug(db_session: Session, slug: str) -> UUID:
    stmt = select(Role.id).where(Role.slug == slug).limit(1)
    role_id = db_session.execute(stmt).scalar_one_or_none()
    assert role_id is not None
    return role_id


def create_user(
    db_session: Session,
    *,
    email: str,
    password: str,
    display_name: str | None = None,
    is_active: bool = True,
    is_service_account: bool = False,
) -> User:
    user = User(
        email=email,
        email_normalized=email.lower(),
        hashed_password=hash_password(password),
        display_name=display_name,
        is_active=is_active,
        is_service_account=is_service_account,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def add_workspace_membership(
    db_session: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    is_default: bool = False,
) -> WorkspaceMembership:
    membership = WorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        is_default=is_default,
    )
    db_session.add(membership)
    db_session.flush()
    return membership


def assign_workspace_role(
    db_session: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    role_slug: str,
) -> UserRoleAssignment:
    rbac = RbacService(session=db_session)
    role_id = role_id_by_slug(db_session, role_slug)
    return rbac.assign_role_if_missing(
        user_id=user_id,
        role_id=role_id,
        workspace_id=workspace_id,
    )


def create_group_with_workspace_role(
    db_session: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    display_name: str,
    slug: str,
    role_slug: str = "workspace-member",
) -> Group:
    rbac = RbacService(session=db_session)
    role_id = role_id_by_slug(db_session, role_slug)
    group = Group(
        display_name=display_name,
        slug=slug,
    )
    db_session.add(group)
    db_session.flush()
    db_session.add(
        GroupMembership(
            group_id=group.id,
            user_id=user_id,
        )
    )
    rbac.assign_principal_role_if_missing(
        principal_type=PrincipalType.GROUP,
        principal_id=group.id,
        role_id=role_id,
        scope_type=AssignmentScopeType.WORKSPACE,
        scope_id=workspace_id,
    )
    db_session.flush()
    return group


__all__ = [
    "add_workspace_membership",
    "assign_workspace_role",
    "create_group_with_workspace_role",
    "create_user",
    "role_id_by_slug",
]
