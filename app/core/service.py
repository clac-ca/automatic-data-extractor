"""Service layer base classes and dependency helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.services.task_queue import TaskQueue


@dataclass(slots=True)
class ServiceContext:
    """Shared context injected into every service instance."""

    settings: Settings
    session: AsyncSession
    request: Request | None = None
    user: Any | None = None
    workspace: Any | None = None
    permissions: frozenset[str] = frozenset()
    task_queue: TaskQueue | None = None

    @property
    def correlation_id(self) -> str | None:
        if self.request is None:
            return None
        return getattr(self.request.state, "correlation_id", None)


class BaseService:
    """Base class for ADE services with contextual utilities."""

    def __init__(self, *, context: ServiceContext) -> None:
        self._context = context

    @property
    def settings(self) -> Settings:
        return self._context.settings

    @property
    def request(self) -> Request | None:
        return self._context.request

    @property
    def session(self) -> AsyncSession:
        return self._context.session

    @property
    def correlation_id(self) -> str | None:
        return self._context.correlation_id

    @property
    def current_user(self) -> Any | None:
        if self._context.user is not None:
            return self._context.user
        if self.request is not None:
            return getattr(self.request.state, "current_user", None)
        return None

    @property
    def current_workspace(self) -> Any | None:
        if self._context.workspace is not None:
            return self._context.workspace
        if self.request is not None:
            return getattr(self.request.state, "current_workspace", None)
        return None

    @property
    def permissions(self) -> frozenset[str]:
        if self._context.permissions:
            return self._context.permissions
        if self.request is not None:
            permissions: frozenset[str] | Iterable[str]
            permissions = getattr(self.request.state, "current_permissions", frozenset())
            if not isinstance(permissions, frozenset):
                permissions = frozenset(permissions)
            return permissions
        return frozenset()

    @property
    def task_queue(self) -> TaskQueue | None:
        return self._context.task_queue

    def require_workspace_id(self) -> str:
        workspace = self.current_workspace
        if workspace is None:
            raise RuntimeError("Workspace context required")
        workspace_id = getattr(workspace, "workspace_id", None) or getattr(
            workspace, "id", None
        )
        if workspace_id is None:
            raise RuntimeError("Workspace identifier missing from context")
        return str(workspace_id)

    async def aclose(self) -> None:
        """Hook for cleaning up resources when the request completes."""

        return None


ServiceT = TypeVar("ServiceT", bound="BaseService")


SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_service_context(
    request: Request,
    session: SessionDependency,
) -> ServiceContext:
    """Aggregate settings and request data for service instantiation."""

    app_settings = getattr(request.app.state, "settings", None)
    settings = app_settings if isinstance(app_settings, Settings) else get_settings()
    user = getattr(request.state, "current_user", None)
    workspace = getattr(request.state, "current_workspace", None)
    permissions_raw: frozenset[str] | Iterable[str]
    permissions_raw = getattr(request.state, "current_permissions", frozenset())
    if isinstance(permissions_raw, frozenset):
        permissions = permissions_raw
    else:
        permissions = frozenset(permissions_raw)
    task_queue = getattr(request.app.state, "task_queue", None)
    queue = task_queue if isinstance(task_queue, TaskQueue) else None

    return ServiceContext(
        settings=settings,
        session=session,
        request=request,
        user=user,
        workspace=workspace,
        permissions=permissions,
        task_queue=queue,
    )


ContextDependency = Annotated[ServiceContext, Depends(get_service_context)]


def service_dependency(
    service_cls: type[ServiceT],
) -> Callable[[ContextDependency], AsyncIterator[ServiceT]]:
    """Return a dependency that yields the requested service class."""

    async def _dependency(
        context: ContextDependency,
    ) -> AsyncIterator[ServiceT]:
        service = service_cls(context=context)
        try:
            yield service
        finally:
            await service.aclose()

    return _dependency


__all__ = [
    "BaseService",
    "ServiceContext",
    "get_service_context",
    "service_dependency",
]

