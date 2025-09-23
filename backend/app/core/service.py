"""Service layer base classes and dependency helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, TypeVar

from fastapi import Depends, Request

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

    async def aclose(self) -> None:
        """Hook for cleaning up resources when the request completes."""

        return None


ServiceT = TypeVar("ServiceT", bound="BaseService")


def get_service_context(
    request: Request,
    settings: AppSettings = Depends(get_settings),
) -> ServiceContext:
    """Aggregate settings and request data for service instantiation."""

    session: AsyncSession | None = getattr(request.state, "db_session", None)
    return ServiceContext(settings=settings, request=request, session=session)


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
