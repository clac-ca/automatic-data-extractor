"""API router composition for the ADE FastAPI application."""

from __future__ import annotations

from fastapi import APIRouter

from .features.auth.router import bootstrap_router, setup_router
from .features.auth.router import router as auth_router
from .features.builds.router import router as builds_router
from .features.configs.router import router as configurations_router
from .features.documents.router import router as documents_router
from .features.health.router import router as health_router
from .features.roles.router import router as roles_router
from .features.runs.router import router as runs_router
from .features.system_settings.router import router as system_router
from .features.users.router import router as users_router
from .features.workspaces.router import router as workspaces_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(setup_router)
api_router.include_router(bootstrap_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(workspaces_router)
api_router.include_router(documents_router)
api_router.include_router(configurations_router)
api_router.include_router(builds_router)
api_router.include_router(runs_router)
api_router.include_router(system_router)

__all__ = ["api_router"]
