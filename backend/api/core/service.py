"""Service layer base classes and dependency helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar

from fastapi import Depends, Request

from backend.app import Settings, get_app_settings

from ..db.session import get_session
from .message_hub import MessageHub
from .task_queue import TaskQueue

try:  # pragma: no cover - optional during type checking
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover - optional import
    AsyncSession = Any  # type: ignore[misc, assignment]


@dataclass(slots=True)
class ServiceContext:
    """Shared context injected into every service instance."""

    settings: Settings
    request: Request | None = None
    session: AsyncSession | None = None
    user: Any | None = None
    workspace: Any | None = None
    permissions: frozenset[str] = frozenset()
    message_hub: MessageHub | None = None
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
    def session(self) -> AsyncSession | None:
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
            permissions = getattr(self.request.state, "current_permissions", frozenset())
            if not isinstance(permissions, frozenset):
                permissions = frozenset(permissions)
            return permissions
        return frozenset()

    @property
    def message_hub(self) -> MessageHub | None:
        return self._context.message_hub

    @property
    def task_queue(self) -> TaskQueue | None:
        return self._context.task_queue

    async def aclose(self) -> None:
        """Hook for cleaning up resources when the request completes."""

        return None

    async def publish_event(
        self,
        name: str,
        payload: Mapping[str, Any] | None = None,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Helper that emits ``name`` with context-aware metadata."""

        combined_metadata = self._build_event_metadata(metadata)
        payload_data = dict(payload or {})

        await self._persist_event(name, payload_data, combined_metadata)

        hub = self._context.message_hub
        if hub is None:
            return

        await hub.publish(
            name,
            payload=payload_data,
            correlation_id=self.correlation_id,
            metadata=combined_metadata,
        )

    def _build_event_metadata(
        self, metadata: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        base: dict[str, Any] = {}
        if metadata:
            base.update(metadata)

        correlation = self.correlation_id
        if correlation and "correlation_id" not in base:
            base["correlation_id"] = correlation

        workspace = self.current_workspace
        if workspace is not None:
            workspace_id = getattr(workspace, "workspace_id", None) or getattr(
                workspace, "id", None
            )
            if workspace_id and "workspace_id" not in base:
                base["workspace_id"] = workspace_id

        user = self.current_user
        if user is not None:
            actor_label = getattr(user, "label", None) or getattr(user, "email", None)
            actor_type = "service_account" if getattr(user, "is_service_account", False) else "user"
            base.setdefault("actor_type", actor_type)
            base.setdefault("actor_id", getattr(user, "id", None))
            if actor_label:
                base.setdefault("actor_label", actor_label)

        return {key: value for key, value in base.items() if value is not None}

    async def _persist_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> None:
        """Allow subclasses to persist emitted events."""

        return None


ServiceT = TypeVar("ServiceT", bound="BaseService")


SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_service_context(
    request: Request,
) -> ServiceContext:
    """Aggregate settings and request data for service instantiation."""

    settings = get_app_settings(request.app)
    session: AsyncSession | None = getattr(request.state, "db_session", None)
    user = getattr(request.state, "current_user", None)
    workspace = getattr(request.state, "current_workspace", None)
    permissions = getattr(request.state, "current_permissions", frozenset())
    message_hub: MessageHub | None = getattr(request.app.state, "message_hub", None)
    task_queue: TaskQueue | None = getattr(request.app.state, "task_queue", None)

    if not isinstance(permissions, frozenset):
        permissions = frozenset(permissions)

    return ServiceContext(
        settings=settings,
        request=request,
        session=session,
        user=user,
        workspace=workspace,
        permissions=permissions,
        message_hub=message_hub,
        task_queue=task_queue,
    )


ContextDependency = Annotated[ServiceContext, Depends(get_service_context)]


def service_dependency(
    service_cls: type[ServiceT],
) -> Callable[[ServiceContext], AsyncIterator[ServiceT]]:
    """Return a dependency that yields the requested service class."""

    async def _dependency(
        session: SessionDependency,
        context: ContextDependency,
    ) -> AsyncIterator[ServiceT]:
        context.session = session
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
