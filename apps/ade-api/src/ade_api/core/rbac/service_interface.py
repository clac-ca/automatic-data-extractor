"""Interface for RBAC operations consumed by feature modules."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.principal import AuthenticatedPrincipal


class RbacService:
    """Interface describing RBAC capabilities.

    Implementations should live in ``features/rbac/service.py`` (or equivalent)
    and accept an ``AsyncSession`` for DB access.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_registry(self) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    async def get_global_role_slugs(  # pragma: no cover - interface only
        self,
        principal: AuthenticatedPrincipal,
    ) -> set[str]:
        raise NotImplementedError

    async def get_global_permissions(  # pragma: no cover - interface only
        self,
        principal: AuthenticatedPrincipal,
    ) -> set[str]:
        raise NotImplementedError

    async def get_workspace_permissions(  # pragma: no cover - interface only
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID | None = None,
    ) -> set[str]:
        raise NotImplementedError

    async def get_effective_permissions(
        self,
        principal: AuthenticatedPrincipal,
        workspace_id: UUID | None = None,
    ) -> set[str]:  # pragma: no cover - interface only
        raise NotImplementedError

    async def has_permission(
        self,
        principal: AuthenticatedPrincipal,
        permission_key: str,
        workspace_id: UUID | None = None,
    ) -> bool:  # pragma: no cover - interface only
        raise NotImplementedError
