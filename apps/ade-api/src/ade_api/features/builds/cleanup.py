"""Placeholder hooks for future environment/document cleanup."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ade_api.settings import Settings

__all__ = ["mark_stale_envs_for_cleanup"]


def mark_stale_envs_for_cleanup(settings: Settings, now: datetime) -> Iterable[str]:
    """
    Placeholder for future cleanup logic.

    Intended future behaviour:
    - identify configuration environments (and documents) older than settings.build_retention
      that have not been used recently.
    - schedule them for deletion and update database metadata.

    Current behaviour:
    - no-op; returns an empty iterable.
    """

    _ = (settings, now)  # silence unused warnings until implemented
    return []
