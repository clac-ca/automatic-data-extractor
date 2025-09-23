"""Service layer for workspace resolution."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status

from ...core.service import BaseService, ServiceContext
from ..users.models import User
from ..users.repository import UsersRepository
from ..users.schemas import UserProfile
from .models import WorkspaceMembership, WorkspaceRole
from .repository import WorkspacesRepository
from .schemas import WorkspaceContext, WorkspaceMember, WorkspaceProfile


_ROLE_PERMISSION_DEFAULTS: dict[WorkspaceRole, frozenset[str]] = {
    WorkspaceRole.MEMBER: frozenset(
        {
            "workspace:read",
            "workspace:documents:read",
            "workspace:documents:write",
        }
    ),
    WorkspaceRole.OWNER: frozenset(
        {
            "workspace:read",
            "workspace:documents:read",
            "workspace:documents:write",
            "workspace:members:read",
            "workspace:members:manage",
            "workspace:settings:manage",
        }
    ),
}

_PERMISSION_IMPLICATIONS: dict[str, frozenset[str]] = {
    "workspace:members:manage": frozenset({"workspace:members:read"}),
}


class WorkspacesService(BaseService):
    """Resolve workspace membership for authenticated users."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("WorkspacesService requires a database session")
        self._repo = WorkspacesRepository(self.session)
        self._users_repo = UsersRepository(self.session)

    async def resolve_selection(
        self,
        *,
        user: User,
        workspace_id: str | None,
    ) -> WorkspaceContext:
        """Return the workspace context for ``user`` using ``workspace_id`` when provided."""

        membership = await self.resolve_membership(user=user, workspace_id=workspace_id)
        return self.build_selection(membership)

    async def list_memberships(self, *, user: User) -> list[WorkspaceProfile]:
        """Return all workspace profiles associated with ``user`` in a stable order."""

        memberships = await self._repo.list_for_user(user.id)
        profiles = [self.build_profile(membership) for membership in memberships]
        profiles.sort(key=lambda profile: (not profile.is_default, profile.slug))
        return profiles

    async def add_member(
        self,
        *,
        workspace_id: str,
        user_id: str,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        """Add ``user_id`` to ``workspace_id`` with the supplied ``role``."""

        workspace = await self._repo.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")

        existing = await self._repo.get_membership(user_id=user_id, workspace_id=workspace_id)
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="User already a workspace member",
            )

        user = await self._users_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

        membership = await self._repo.create_membership(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        return self.build_member(membership)

    async def resolve_membership(
        self, *, user: User, workspace_id: str | None
    ) -> WorkspaceMembership:
        """Return the ``WorkspaceMembership`` link for ``user`` and ``workspace_id``."""

        return await self._resolve_membership(user_id=user.id, workspace_id=workspace_id)

    async def _resolve_membership(
        self, *, user_id: str, workspace_id: str | None
    ) -> WorkspaceMembership:
        if workspace_id:
            membership = await self._repo.get_membership(
                user_id=user_id, workspace_id=workspace_id
            )
            if membership is None:
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
            return membership

        membership = await self._repo.get_default_membership(user_id=user_id)
        if membership is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No workspace assigned")
        return membership

    def build_selection(self, membership: WorkspaceMembership) -> WorkspaceContext:
        """Construct a ``WorkspaceContext`` from a membership record."""

        profile = self.build_profile(membership)
        self._context.workspace = profile
        self._context.permissions = frozenset(profile.permissions)
        return WorkspaceContext(workspace=profile)

    def build_profile(self, membership: WorkspaceMembership) -> WorkspaceProfile:
        workspace = membership.workspace
        if workspace is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workspace missing"
            )

        permissions = self._merge_permissions(membership.role, membership.permissions)
        return WorkspaceProfile(
            workspace_id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            role=membership.role,
            permissions=sorted(permissions),
            is_default=bool(membership.is_default),
        )

    def build_member(self, membership: WorkspaceMembership) -> WorkspaceMember:
        user = membership.user
        if user is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Member user missing"
            )

        permissions = self._merge_permissions(membership.role, membership.permissions)
        return WorkspaceMember(
            workspace_membership_id=membership.id,
            workspace_id=membership.workspace_id,
            role=membership.role,
            permissions=sorted(permissions),
            is_default=bool(membership.is_default),
            user=UserProfile.model_validate(user),
        )

    @staticmethod
    def _merge_permissions(role: WorkspaceRole, custom: Iterable[str] | None) -> set[str]:
        base = _ROLE_PERMISSION_DEFAULTS.get(role, frozenset())
        combined = set(base)
        if custom:
            combined.update(custom)

        updated = True
        while updated:
            updated = False
            for source, implied in _PERMISSION_IMPLICATIONS.items():
                if source in combined and not implied.issubset(combined):
                    combined.update(implied)
                    updated = True

        return combined


__all__ = ["WorkspacesService"]
