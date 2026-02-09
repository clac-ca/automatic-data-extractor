"""Service layer for the health module."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import ValidationError

from ade_api.common.logging import log_context
from ade_api.features.admin_settings.service import (
    RuntimeSettingsService,
    RuntimeSettingsV2,
    resolve_runtime_settings_from_env_defaults,
)
from ade_api.settings import Settings

from .exceptions import HealthCheckError
from .schemas import HealthCheckResponse, HealthComponentStatus

logger = logging.getLogger(__name__)


class HealthService:
    """Compute health responses for readiness/liveness checks."""

    def __init__(
        self,
        *,
        settings: Settings,
        runtime_settings_service: RuntimeSettingsService | None = None,
    ) -> None:
        self._settings = settings
        self._runtime_settings_service = runtime_settings_service

    def status(self) -> HealthCheckResponse:
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

            runtime = self._runtime_settings()
            if runtime.safe_mode.enabled:
                components.append(
                    HealthComponentStatus(
                        name="safe-mode",
                        status="degraded",
                        detail=runtime.safe_mode.detail,
                    )
                )
                logger.warning(
                    "health.status.degraded_safe_mode",
                    extra=log_context(
                        safe_mode_enabled=True,
                        safe_mode_detail=runtime.safe_mode.detail,
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
                    safe_mode_enabled=runtime.safe_mode.enabled,
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

    def _runtime_settings(self) -> RuntimeSettingsV2:
        if self._runtime_settings_service is not None:
            logger.debug(
                "health.runtime_settings.fetch_from_service",
                extra=log_context(
                    source="service",
                ),
            )
            return self._runtime_settings_service.get_effective_values()

        logger.debug(
            "health.runtime_settings.derived_from_env_settings",
            extra=log_context(
                source="settings",
                safe_mode_enabled=self._settings.safe_mode,
            ),
        )
        # This fallback is for health probe paths that do not wire DB dependencies.
        return resolve_runtime_settings_from_env_defaults(self._settings)
