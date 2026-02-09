"""Password reset delivery adapters."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol

logger = logging.getLogger(__name__)


class PasswordResetDelivery(Protocol):
    """Delivery interface for reset tokens."""

    def send_reset(self, *, email: str, token: str, expires_at: datetime) -> None: ...


class NoopPasswordResetDelivery:
    """No-op reset delivery used until SMTP is configured."""

    def send_reset(self, *, email: str, token: str, expires_at: datetime) -> None:
        # Deliberately avoid logging the raw token.
        logger.info(
            "auth.password_reset.delivery.noop",
            extra={
                "email": email,
                "expires_at": expires_at.isoformat(),
                "token_preview": f"{token[:6]}...{token[-4:]}" if len(token) > 12 else "redacted",
            },
        )
