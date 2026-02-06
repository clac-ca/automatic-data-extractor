"""Routes exposing ADE metadata."""

from fastapi import APIRouter, status

from ade_api.infra.versions import installed_version, read_web_version
from ade_api.settings import get_settings

from .schemas import VersionsResponse

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get(
    "/versions",
    response_model=VersionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Installed ADE versions",
)
def read_versions() -> VersionsResponse:
    """Return installed backend, engine-parent marker/version, and web versions."""

    settings = get_settings()
    engine_parent_version = installed_version("ade-engine", "ade_engine")
    return VersionsResponse(
        backend=settings.app_version,
        engine=engine_parent_version if engine_parent_version != "unknown" else "per-config",
        web=read_web_version(settings.web_version_file),
    )


__all__ = ["router"]
