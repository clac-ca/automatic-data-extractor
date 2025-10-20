"""Service layer for the health module."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.platform.config import Settings

from .exceptions import HealthCheckError
from .schemas import HealthCheckResponse, HealthComponentStatus


class HealthService:
    """Compute health responses for readiness/liveness checks."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

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
                        detail=f"v{self._settings.app_version}",
                    ),
                ],
            )
        except Exception as exc:  # pragma: no cover - defensive guardrail
            raise HealthCheckError("Failed to compute health status") from exc
