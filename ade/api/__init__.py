"""API shell package for ADE."""

from . import deps
from .v1.router import router as v1_router

__all__ = ["deps", "v1_router"]
