"""Central router registration for the ADE backend."""

from fastapi import APIRouter, FastAPI

from .modules.auth.router import router as auth_router
from .modules.documents.router import router as documents_router
from .modules.health.router import router as health_router
from .modules.workspaces.router import router as workspaces_router
from .modules.users.router import router as users_router


api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(workspaces_router)
api_router.include_router(documents_router)


def register_routers(app: FastAPI) -> None:
    """Attach all module routers to the FastAPI application."""
    app.include_router(api_router)
