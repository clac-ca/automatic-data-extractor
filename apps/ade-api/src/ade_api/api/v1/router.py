"""API router composition for the ADE FastAPI application."""

from __future__ import annotations

from fastapi import APIRouter

from ade_api.features.api_keys.router import router as api_keys_router
from ade_api.features.auth.router import router as auth_router
from ade_api.features.builds.router import router as builds_router
from ade_api.features.configs.router import router as configurations_router
from ade_api.features.documents.router import router as documents_router
from ade_api.features.health.router import router as health_router
from ade_api.features.jobs.router import router as jobs_router
from ade_api.features.me.router import router as me_router
from ade_api.features.rbac.router import router as rbac_router
from ade_api.features.rbac.router import user_roles_router as rbac_user_roles_router
from ade_api.features.runs.router import router as runs_router
from ade_api.features.system_settings.router import router as system_router
from ade_api.features.users.router import router as users_router
from ade_api.features.workspaces.members import router as workspace_members_router
from ade_api.features.workspaces.router import router as workspaces_router
from ade_api.meta.router import router as meta_router

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
api_router.include_router(jobs_router)
api_router.include_router(builds_router)
api_router.include_router(runs_router)
api_router.include_router(system_router)

__all__ = ["api_router"]
