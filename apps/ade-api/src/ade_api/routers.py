"""API router composition for the ADE FastAPI application."""

from __future__ import annotations

from fastapi import APIRouter

from .features.api_keys.router import router as api_keys_router
from .features.auth.router import router as auth_router
from .features.builds.router import router as builds_router
from .features.configs.router import router as configurations_router
from .features.documents.router import router as documents_router
from .features.health.router import router as health_router
from .features.me.router import router as me_router
from .features.rbac.router import (
    router as rbac_router,
)
from .features.rbac.router import (
    user_roles_router as rbac_user_roles_router,
)
from .features.runs.router import router as runs_router
from .features.system_settings.router import router as system_router
from .features.users.router import router as users_router
from .features.workspaces.members_router import router as workspace_members_router
from .features.workspaces.router import router as workspaces_router
from .meta.router import router as meta_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(meta_router)
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(api_keys_router)
api_router.include_router(users_router)
api_router.include_router(rbac_router, prefix="/rbac")
api_router.include_router(rbac_user_roles_router)
api_router.include_router(me_router)
api_router.include_router(workspaces_router)
api_router.include_router(workspace_members_router)
api_router.include_router(documents_router)
api_router.include_router(configurations_router)
api_router.include_router(builds_router)
api_router.include_router(runs_router)
api_router.include_router(system_router)

__all__ = ["api_router"]
