"""Routes exposing ADE metadata."""

from fastapi import APIRouter, status

from ade_api.infra.versions import installed_version

from .schemas import VersionsResponse

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get(
    "/versions",
    response_model=VersionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Installed ADE versions",
)
def read_versions() -> VersionsResponse:
    """Return installed ade-api and ade-engine versions."""

    return VersionsResponse(
        ade_api=installed_version("ade-api", "ade_api"),
        ade_engine=installed_version("ade-engine", "ade_engine"),
    )


__all__ = ["router"]
