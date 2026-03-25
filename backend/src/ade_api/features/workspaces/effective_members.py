from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, false, select, true
from sqlalchemy.orm import Session

from ade_api.features.rbac.service import RbacService
from ade_api.settings import Settings
from ade_db.models import (
    AssignmentScopeType,
    Group,
    GroupMembership,
    Permission,
    PrincipalType,
    Role,
    RoleAssignment,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
)


@dataclass(slots=True)
class EffectiveWorkspaceMemberSource:
    principal_type: PrincipalType
    principal_id: UUID
    principal_display_name: str | None
    principal_email: str | None
    principal_slug: str | None
    role_map: dict[UUID, str] = field(default_factory=dict)
    created_at: datetime | None = None

    def add_role(self, *, role_id: UUID, role_slug: str, created_at: datetime) -> None:
        self.role_map.setdefault(role_id, role_slug)
        if self.created_at is None or created_at < self.created_at:
            self.created_at = created_at


@dataclass(slots=True)
class EffectiveWorkspaceMember:
    user: User
    source_map: dict[tuple[PrincipalType, UUID], EffectiveWorkspaceMemberSource] = field(
        default_factory=dict
    )
    role_map: dict[UUID, str] = field(default_factory=dict)
    created_at: datetime | None = None

    def add_source_role(
        self,
        *,
        principal_type: PrincipalType,
        principal_id: UUID,
        principal_display_name: str | None,
        principal_email: str | None,
        principal_slug: str | None,
        role_id: UUID,
        role_slug: str,
        created_at: datetime,
    ) -> None:
        key = (principal_type, principal_id)
        source = self.source_map.get(key)
        if source is None:
            source = EffectiveWorkspaceMemberSource(
                principal_type=principal_type,
                principal_id=principal_id,
                principal_display_name=principal_display_name,
                principal_email=principal_email,
                principal_slug=principal_slug,
            )
            self.source_map[key] = source
        source.add_role(role_id=role_id, role_slug=role_slug, created_at=created_at)
        self.role_map.setdefault(role_id, role_slug)
        if self.created_at is None or created_at < self.created_at:
            self.created_at = created_at

    @property
    def has_direct_access(self) -> bool:
        return (PrincipalType.USER, self.user.id) in self.source_map

    @property
    def has_indirect_access(self) -> bool:
        return any(
            source.principal_type == PrincipalType.GROUP for source in self.source_map.values()
        )


def workspace_access_role_filter(role_id_column: object) -> object:
    """Return a predicate matching roles that grant workspace-scoped access."""

    return (
        select(RolePermission.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            RolePermission.role_id == role_id_column,
            Permission.scope_type == ScopeType.WORKSPACE,
        )
        .exists()
    )


def role_grants_workspace_access(role: Role) -> bool:
    """Return True when ``role`` has at least one workspace-scoped permission."""

    return any(
        assignment.permission is not None
        and assignment.permission.scope_type == ScopeType.WORKSPACE
        for assignment in role.permissions
    )


class EffectiveWorkspaceMembersResolver:
    """Resolve active human workspace members from effective access grants."""

    def __init__(self, *, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings
        self._rbac = RbacService(session=session)

    def list_members(
        self,
        *,
        workspace_id: UUID,
        user_ids: Sequence[UUID] | None = None,
    ) -> list[EffectiveWorkspaceMember]:
        requested_ids = None
        if user_ids is not None:
            requested_ids = {UUID(str(user_id)) for user_id in user_ids}
            if not requested_ids:
                return []
        members: dict[UUID, EffectiveWorkspaceMember] = {}

        for assignment, user, role in self._legacy_direct_assignments(
            workspace_id=workspace_id,
            user_ids=requested_ids,
        ):
            member = members.setdefault(user.id, EffectiveWorkspaceMember(user=user))
            member.add_source_role(
                principal_type=PrincipalType.USER,
                principal_id=user.id,
                principal_display_name=user.display_name,
                principal_email=user.email,
                principal_slug=None,
                role_id=role.id,
                role_slug=role.slug,
                created_at=assignment.created_at,
            )

        for assignment, user, role in self._direct_principal_assignments(
            workspace_id=workspace_id,
            user_ids=requested_ids,
        ):
            member = members.setdefault(user.id, EffectiveWorkspaceMember(user=user))
            member.add_source_role(
                principal_type=PrincipalType.USER,
                principal_id=user.id,
                principal_display_name=user.display_name,
                principal_email=user.email,
                principal_slug=None,
                role_id=role.id,
                role_slug=role.slug,
                created_at=assignment.created_at,
            )

        for assignment, group, membership, user, role in self._group_assignments(
            workspace_id=workspace_id,
            user_ids=requested_ids,
        ):
            effective_created_at = max(assignment.created_at, membership.created_at)
            member = members.setdefault(user.id, EffectiveWorkspaceMember(user=user))
            member.add_source_role(
                principal_type=PrincipalType.GROUP,
                principal_id=group.id,
                principal_display_name=group.display_name,
                principal_email=None,
                principal_slug=group.slug,
                role_id=role.id,
                role_slug=role.slug,
                created_at=effective_created_at,
            )

        effective_members = list(members.values())

        effective_members.sort(
            key=lambda member: (
                self.display_label(member).lower(),
                str(member.user.id),
            )
        )
        return effective_members

    def member_by_user_id(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> EffectiveWorkspaceMember | None:
        members = self.list_members(workspace_id=workspace_id, user_ids=[user_id])
        return members[0] if members else None

    @staticmethod
    def display_label(member: EffectiveWorkspaceMember) -> str:
        return member.user.display_name or member.user.email or str(member.user.id)

    def _legacy_direct_assignments(
        self,
        *,
        workspace_id: UUID,
        user_ids: set[UUID] | None,
    ) -> Iterable[tuple[UserRoleAssignment, User, Role]]:
        stmt = (
            select(UserRoleAssignment, User, Role)
            .join(User, UserRoleAssignment.user_id == User.id)
            .join(Role, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.workspace_id == workspace_id,
                workspace_access_role_filter(UserRoleAssignment.role_id),
                User.is_active == true(),
                User.is_service_account == false(),
            )
        )
        if user_ids:
            stmt = stmt.where(UserRoleAssignment.user_id.in_(user_ids))
        return self._session.execute(stmt).all()

    def _direct_principal_assignments(
        self,
        *,
        workspace_id: UUID,
        user_ids: set[UUID] | None,
    ) -> Iterable[tuple[RoleAssignment, User, Role]]:
        stmt = (
            select(RoleAssignment, User, Role)
            .join(
                User,
                and_(
                    RoleAssignment.principal_type == PrincipalType.USER,
                    RoleAssignment.principal_id == User.id,
                ),
            )
            .join(Role, RoleAssignment.role_id == Role.id)
            .where(
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
                RoleAssignment.principal_type == PrincipalType.USER,
                workspace_access_role_filter(RoleAssignment.role_id),
                User.is_active == true(),
                User.is_service_account == false(),
            )
        )
        if user_ids:
            stmt = stmt.where(RoleAssignment.principal_id.in_(user_ids))
        return self._session.execute(stmt).all()

    def _group_assignments(
        self,
        *,
        workspace_id: UUID,
        user_ids: set[UUID] | None,
    ) -> Iterable[tuple[RoleAssignment, Group, GroupMembership, User, Role]]:
        stmt = (
            select(RoleAssignment, Group, GroupMembership, User, Role)
            .join(
                Group,
                and_(
                    RoleAssignment.principal_type == PrincipalType.GROUP,
                    RoleAssignment.principal_id == Group.id,
                ),
            )
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .join(User, GroupMembership.user_id == User.id)
            .join(Role, RoleAssignment.role_id == Role.id)
            .where(
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
                RoleAssignment.principal_type == PrincipalType.GROUP,
                workspace_access_role_filter(RoleAssignment.role_id),
                Group.is_active == true(),
                self._rbac.build_group_source_filter(),
                User.is_active == true(),
                User.is_service_account == false(),
            )
        )
        if user_ids:
            stmt = stmt.where(User.id.in_(user_ids))
        return self._session.execute(stmt).all()


__all__ = [
    "EffectiveWorkspaceMember",
    "EffectiveWorkspaceMemberSource",
    "EffectiveWorkspaceMembersResolver",
    "role_grants_workspace_access",
    "workspace_access_role_filter",
]
