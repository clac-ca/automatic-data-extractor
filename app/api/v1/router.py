"""Version 1 API router composition."""

from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.configurations.router import router as configurations_router
from app.features.documents.router import router as documents_router
from app.features.health.router import router as health_router
from app.features.jobs.router import router as jobs_router
from app.features.users.router import router as users_router
from app.features.workspaces.router import router as workspaces_router

router = APIRouter()

router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(workspaces_router)
router.include_router(configurations_router)
router.include_router(documents_router)
router.include_router(jobs_router)

__all__ = ["router"]
