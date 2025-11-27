"""Service layer for the health module."""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from pydantic import ValidationError

from ade_api.features.system_settings.schemas import SafeModeStatus
from ade_api.features.system_settings.service import (
    SAFE_MODE_DEFAULT_DETAIL,
    SafeModeService,
)
from ade_api.settings import Settings
from ade_api.shared.core.logging import log_context

from .exceptions import HealthCheckError
from .schemas import HealthCheckResponse, HealthComponentStatus

logger = logging.getLogger(__name__)


class HealthService:
    """Compute health responses for readiness/liveness checks."""

    def __init__(
        self,
        *,
        settings: Settings,
        safe_mode_service: SafeModeService | None = None,
    ) -> None:
        self._settings = settings
        self._safe_mode_service = safe_mode_service

    async def status(self) -> HealthCheckResponse:
        """Return the overall system health."""
        logger.debug(
            "health.status.start",
            extra=log_context(
                app_version=self._settings.app_version,
                safe_mode_default=bool(self._settings.safe_mode),
            ),
        )

        try:
            components: list[HealthComponentStatus] = [
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
                logger.warning(
                    "health.status.degraded_safe_mode",
                    extra=log_context(
                        safe_mode_enabled=True,
                        safe_mode_detail=safe_mode.detail,
                    ),
                )

            response = HealthCheckResponse(
                status="ok",
                timestamp=datetime.now(tz=UTC),
                components=components,
            )

            logger.info(
                "health.status.success",
                extra=log_context(
                    status=response.status,
                    component_count=len(response.components),
                    safe_mode_enabled=safe_mode.enabled,
                ),
            )
            return response

        except ValidationError as exc:  # pragma: no cover - defensive guardrail
            logger.exception(
                "health.status.validation_error",
                extra=log_context(
                    app_version=self._settings.app_version,
                ),
            )
            raise HealthCheckError("Failed to compute health status") from exc

    async def _safe_mode_status(self) -> SafeModeStatus:
        if self._safe_mode_service is not None:
            logger.debug(
                "health.safe_mode.fetch_from_service",
                extra=log_context(
                    source="service",
                ),
            )
            return await self._safe_mode_service.get_status()

        logger.debug(
            "health.safe_mode.derived_from_settings",
            extra=log_context(
                source="settings",
                safe_mode_enabled=self._settings.safe_mode,
            ),
        )
        return SafeModeStatus(
            enabled=self._settings.safe_mode,
            detail=SAFE_MODE_DEFAULT_DETAIL,
        )
