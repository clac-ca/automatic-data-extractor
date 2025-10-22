"""Version 1 API router composition."""

from fastapi import APIRouter

from backend.app.features.auth.router import router as auth_router, setup_router
from backend.app.features.configurations.router import router as configurations_router
from backend.app.features.documents.router import router as documents_router
from backend.app.features.health.router import router as health_router
from backend.app.features.jobs.router import router as jobs_router
from backend.app.features.roles.router import router as roles_router
from backend.app.features.users.router import router as users_router
from backend.app.features.workspaces.router import router as workspaces_router

router = APIRouter(prefix="/v1")

router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(setup_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(workspaces_router)
router.include_router(configurations_router)
router.include_router(documents_router)
router.include_router(jobs_router)

__all__ = ["router"]
