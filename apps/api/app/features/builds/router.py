"""HTTP endpoints for managing configuration build environments."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Security, status

from apps.api.app.shared.dependency import (
    get_builds_service,
    require_authenticated,
    require_csrf,
    require_workspace,
)

from ..users.models import User
from .exceptions import BuildAlreadyInProgressError, BuildExecutionError, BuildNotFoundError
from .models import BuildStatus
from .schemas import BuildEnsureRequest, BuildEnsureResponse, BuildRecord
from .service import BuildEnsureMode, BuildsService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/configurations/{config_id}",
    tags=["builds"],
    dependencies=[Security(require_authenticated)],
)

BUILD_BODY = Body(
    BuildEnsureRequest(),
    description="Options for ensuring the configuration build is up-to-date.",
)


@router.get(
    "/build",
    response_model=BuildRecord,
    response_model_exclude_none=True,
    summary="Get the active build pointer",
)
async def get_build(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[BuildsService, Depends(get_builds_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> BuildRecord:
    try:
        build = await service.get_active_build(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except BuildNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="build_not_found") from exc
    return BuildRecord.model_validate(build)


@router.put(
    "/build",
    response_model=BuildEnsureResponse,
    response_model_exclude_none=True,
    dependencies=[Security(require_csrf)],
    summary="Ensure the configuration build exists and is current",
)
async def ensure_build(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[BuildsService, Depends(get_builds_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: BuildEnsureRequest = BUILD_BODY,
) -> BuildEnsureResponse:
    mode = BuildEnsureMode.BLOCKING if payload.wait else BuildEnsureMode.INTERACTIVE
    try:
        result = await service.ensure_build(
            workspace_id=workspace_id,
            config_id=config_id,
            force=payload.force,
            mode=mode,
        )
    except BuildAlreadyInProgressError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="build_in_progress") from exc
    except BuildExecutionError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="build_failed") from exc
    except BuildNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="build_not_found") from exc

    if result.build is None:
        return BuildEnsureResponse(status=BuildStatus.BUILDING)

    return BuildEnsureResponse(
        status=result.status,
        build=BuildRecord.model_validate(result.build),
    )


@router.delete(
    "/build",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(require_csrf)],
    summary="Delete the active build and remove its virtual environment",
)
async def delete_build(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[BuildsService, Depends(get_builds_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    try:
        await service.delete_active_build(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except BuildNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="build_not_found") from exc
