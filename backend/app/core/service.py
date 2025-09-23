"""Service layer base classes and dependency helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, FrozenSet, Mapping, TypeVar

from fastapi import Depends, Request

from .message_hub import MessageHub
from .settings import AppSettings, get_settings

try:  # pragma: no cover - optional during type checking
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover - optional import
    AsyncSession = Any  # type: ignore[misc, assignment]


@dataclass(slots=True)
class ServiceContext:
    """Shared context injected into every service instance."""

    settings: AppSettings
    request: Request | None = None
    session: AsyncSession | None = None
    user: Any | None = None
    service_account: Any | None = None
    workspace: Any | None = None
    permissions: FrozenSet[str] = frozenset()
    message_hub: MessageHub | None = None

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
    def settings(self) -> AppSettings:
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
    def current_service_account(self) -> Any | None:
        if self._context.service_account is not None:
            return self._context.service_account
        if self.request is not None:
            return getattr(self.request.state, "current_service_account", None)
        return None

    @property
    def current_workspace(self) -> Any | None:
        if self._context.workspace is not None:
            return self._context.workspace
        if self.request is not None:
            return getattr(self.request.state, "current_workspace", None)
        return None

    @property
    def permissions(self) -> FrozenSet[str]:
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

        hub = self._context.message_hub
        if hub is None:
            return

        combined_metadata = self._build_event_metadata(metadata)
        await hub.publish(
            name,
            payload=payload or {},
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
            base.setdefault("actor_type", "user")
            base.setdefault("actor_id", getattr(user, "id", None))
            base.setdefault("actor_label", getattr(user, "email", None))
        else:
            service_account = self.current_service_account
            if service_account is not None:
                base.setdefault("actor_type", "service_account")
                base.setdefault("actor_id", getattr(service_account, "id", None))
                base.setdefault(
                    "actor_label", getattr(service_account, "display_name", None)
                )

        return {key: value for key, value in base.items() if value is not None}


ServiceT = TypeVar("ServiceT", bound="BaseService")


def get_service_context(
    request: Request,
    settings: AppSettings = Depends(get_settings),
) -> ServiceContext:
    """Aggregate settings and request data for service instantiation."""

    session: AsyncSession | None = getattr(request.state, "db_session", None)
    user = getattr(request.state, "current_user", None)
    service_account = getattr(request.state, "current_service_account", None)
    workspace = getattr(request.state, "current_workspace", None)
    permissions = getattr(request.state, "current_permissions", frozenset())
    message_hub: MessageHub | None = getattr(request.app.state, "message_hub", None)

    if not isinstance(permissions, frozenset):
        permissions = frozenset(permissions)

    return ServiceContext(
        settings=settings,
        request=request,
        session=session,
        user=user,
        service_account=service_account,
        workspace=workspace,
        permissions=permissions,
        message_hub=message_hub,
    )


def service_dependency(service_cls: type[ServiceT]) -> Callable[[ServiceContext], AsyncIterator[ServiceT]]:
    """Return a dependency that yields the requested service class."""

    async def _dependency(
        context: ServiceContext = Depends(get_service_context),
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
