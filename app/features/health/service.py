"""Service layer for the health module."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.service import BaseService

from .exceptions import HealthCheckError
from .schemas import HealthCheckResponse, HealthComponentStatus


class HealthService(BaseService):
    """Compute health responses for readiness/liveness checks."""

    async def status(self) -> HealthCheckResponse:
        """Return the overall system health."""
        try:
            return HealthCheckResponse(
                status="ok",
                timestamp=datetime.now(tz=UTC),
                components=[
                    HealthComponentStatus(
                        name="api",
                        status="available",
                        detail=f"v{self.settings.app_version}",
                    ),
                ],
            )
        except Exception as exc:  # pragma: no cover - defensive guardrail
            raise HealthCheckError("Failed to compute health status") from exc
