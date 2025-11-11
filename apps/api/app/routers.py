"""API router composition for the ADE FastAPI application."""

from __future__ import annotations

from fastapi import APIRouter

from .features.auth.router import router as auth_router
from .features.auth.router import setup_router
from .features.configs.router import router as configs_router
from .features.documents.router import router as documents_router
from .features.health.router import router as health_router
from .features.roles.router import router as roles_router
from .features.users.router import router as users_router
from .features.workspaces.router import router as workspaces_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(setup_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(workspaces_router)
api_router.include_router(documents_router)
api_router.include_router(configs_router)

__all__ = ["api_router"]
