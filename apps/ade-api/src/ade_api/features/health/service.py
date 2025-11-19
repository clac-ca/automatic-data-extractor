"""Service layer for the health module."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError

from ade_api.features.system_settings.schemas import SafeModeStatus
from ade_api.features.system_settings.service import SAFE_MODE_DEFAULT_DETAIL, SafeModeService
from ade_api.settings import Settings

from .exceptions import HealthCheckError
from .schemas import HealthCheckResponse, HealthComponentStatus


class HealthService:
    """Compute health responses for readiness/liveness checks."""

    def __init__(
        self, *, settings: Settings, safe_mode_service: SafeModeService | None = None
    ) -> None:
        self._settings = settings
        self._safe_mode_service = safe_mode_service

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
            safe_mode = await self._safe_mode_status()
            if safe_mode.enabled:
                components.append(
                    HealthComponentStatus(
                        name="safe-mode",
                        status="degraded",
                        detail=safe_mode.detail,
                    )
                )
            return HealthCheckResponse(
                status="ok",
                timestamp=datetime.now(tz=UTC),
                components=components,
            )
        except ValidationError as exc:  # pragma: no cover - defensive guardrail
            raise HealthCheckError("Failed to compute health status") from exc

    async def _safe_mode_status(self) -> SafeModeStatus:
        if self._safe_mode_service is not None:
            return await self._safe_mode_service.get_status()
        return SafeModeStatus(enabled=self._settings.safe_mode, detail=SAFE_MODE_DEFAULT_DETAIL)
