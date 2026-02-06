"""Routes exposing ADE metadata."""

from fastapi import APIRouter, status

from ade_api.infra.versions import read_web_version
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
    """Return installed backend/web versions and worker engine resolution mode."""

    settings = get_settings()
    return VersionsResponse(
        backend=settings.app_version,
        engine="per-config",
        web=read_web_version(settings.web_version_file),
    )


__all__ = ["router"]
