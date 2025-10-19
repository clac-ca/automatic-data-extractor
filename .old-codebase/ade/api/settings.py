"""Settings helpers exposed as FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from ade.platform.config import Settings, get_settings


def get_app_settings(request: Request) -> Settings:
    """Return the application settings cached on the FastAPI app."""

    state = getattr(request.app, "state", None)
    settings = getattr(state, "settings", None)
    if isinstance(settings, Settings):
        return settings

    refreshed = get_settings()
    if state is not None:
        state.settings = refreshed
    return refreshed


__all__ = ["get_app_settings"]
