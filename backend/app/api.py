"""Central router registration for the ADE backend."""

from fastapi import APIRouter, FastAPI

from .modules.health.router import router as health_router


api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])


def register_routers(app: FastAPI) -> None:
    """Attach all module routers to the FastAPI application."""
    app.include_router(api_router)
