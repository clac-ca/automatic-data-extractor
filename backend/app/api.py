"""Central router registration for the ADE backend."""

from fastapi import APIRouter, FastAPI

from .modules.auth.router import router as auth_router
from .modules.configurations.router import router as configurations_router
from .modules.documents.router import router as documents_router
from .modules.health.router import router as health_router
from .modules.jobs.router import router as jobs_router
from .modules.workspaces.router import router as workspaces_router
from .modules.results.router import router as results_router
from .modules.users.router import router as users_router


api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(workspaces_router)
api_router.include_router(configurations_router)
api_router.include_router(documents_router)
api_router.include_router(jobs_router)
api_router.include_router(results_router)


def register_routers(app: FastAPI) -> None:
    """Attach all module routers to the FastAPI application."""
    app.include_router(api_router)
