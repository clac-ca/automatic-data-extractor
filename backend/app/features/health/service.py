"""Service layer for the health module."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.shared.core.config import Settings

from .exceptions import HealthCheckError
from .schemas import HealthCheckResponse, HealthComponentStatus

SAFE_MODE_DISABLED_MESSAGE = (
    "User-submitted configuration execution is currently disabled because ADE_SAFE_MODE is enabled."
)


class HealthService:
    """Compute health responses for readiness/liveness checks."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    async def status(self) -> HealthCheckResponse:
        """Return the overall system health."""
        try:
            components = [
                HealthComponentStatus(
                    name="api",
                    status="available",
                    detail=f"v{self._settings.app_version}",
                ),
            ]
            if self._settings.safe_mode:
                components.append(
                    HealthComponentStatus(
                        name="safe-mode",
                        status="degraded",
                        detail=SAFE_MODE_DISABLED_MESSAGE,
                    )
                )
            return HealthCheckResponse(
                status="ok",
                timestamp=datetime.now(tz=UTC),
                components=components,
            )
        except Exception as exc:  # pragma: no cover - defensive guardrail
            raise HealthCheckError("Failed to compute health status") from exc
