"""Placeholder service for the rebuilt jobs module."""

from __future__ import annotations

from ...core.service import BaseService, ServiceContext


class JobsService(BaseService):
    """Service stub retained while the jobs module is rewritten."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        raise NotImplementedError(
            "JobsService will be implemented as part of the backend rewrite. "
            "See BACKEND_REWRITE_PLAN.md for the current plan."
        )


__all__ = ["JobsService"]

