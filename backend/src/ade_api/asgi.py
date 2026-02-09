"""ASGI compatibility module for hosts that require an application object."""

from __future__ import annotations

from .main import create_app

app = create_app()

__all__ = ["app"]
