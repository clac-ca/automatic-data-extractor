"""Version 1 API router composition."""

from fastapi import APIRouter

from apps.api.app.features.auth.router import router as auth_router
from apps.api.app.features.auth.router import setup_router
from apps.api.app.features.documents.router import router as documents_router
from apps.api.app.features.health.router import router as health_router
from apps.api.app.features.roles.router import router as roles_router
from apps.api.app.features.users.router import router as users_router
from apps.api.app.features.workspaces.router import router as workspaces_router

router = APIRouter(prefix="/v1")

router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(setup_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(workspaces_router)
router.include_router(documents_router)

__all__ = ["router"]
