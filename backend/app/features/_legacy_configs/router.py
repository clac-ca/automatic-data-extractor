"""FastAPI router exposing configuration package APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from backend.app.features.auth.dependencies import require_authenticated, require_csrf
from backend.app.features.roles.dependencies import require_workspace
from backend.app.shared.core.schema import ErrorMessage

from ..users.models import User
from .dependencies import get_config_service
from .exceptions import (
    ConfigDependentJobsError,
    ConfigInvariantViolationError,
    ConfigNotFoundError,
    ConfigSlugConflictError,
    ConfigVersionActivationError,
    ConfigVersionDependentJobsError,
    ConfigVersionNotFoundError,
    ManifestValidationError,
    VersionFileConflictError,
    VersionFileNotFoundError,
)
from .schemas import (
    ConfigCreateRequest,
    ConfigRecord,
    ConfigScriptContent,
    ConfigScriptCreateRequest,
    ConfigScriptSummary,
    ConfigScriptUpdateRequest,
    ConfigVersionCreateRequest,
    ConfigVersionRecord,
    ConfigVersionTestRequest,
    ConfigVersionTestResponse,
    ConfigVersionValidateResponse,
    ManifestPatchRequest,
    ManifestResponse,
)
from .service import ConfigService

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["configs"],
    dependencies=[Security(require_authenticated)],
)

CONFIG_CREATE_BODY = Body(...)
VERSION_CREATE_BODY = Body(...)
CLONE_BODY = Body(...)
SCRIPT_CREATE_BODY = Body(...)
SCRIPT_UPDATE_BODY = Body(...)
MANIFEST_UPDATE_BODY = Body(...)
TEST_BODY = Body(...)


def _api_error(code: str, message: str, details: dict[str, object] | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "details": details}


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/configs",
    response_model=list[ConfigRecord],
    status_code=status.HTTP_200_OK,
    summary="List configuration packages for a workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
    },
)
async def list_configs(
    workspace_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    include_deleted: Annotated[
        bool,
        Query(description="Include archived configs in the response."),
    ] = False,
) -> list[ConfigRecord]:
    return await service.list_configs(
        workspace_id=workspace_id,
        include_deleted=include_deleted,
    )


@router.post(
    "/configs",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration package",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def create_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigCreateRequest = CONFIG_CREATE_BODY,
    response: Response,
) -> ConfigRecord:
    try:
        record = await service.create_config(
            workspace_id=workspace_id,
            slug=payload.slug,
            title=payload.title,
            actor_id=str(actor.id),
        )
    except ConfigSlugConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error("slug_conflict", str(exc)),
        ) from exc
    response.headers["Location"] = f"/api/v1/workspaces/{workspace_id}/configs/{record.config_id}"
    return record


@router.get(
    "/configs/{config_id}",
    response_model=ConfigRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve configuration details",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    include_deleted: Annotated[
        bool,
        Query(description="Include archived config metadata."),
    ] = False,
) -> ConfigRecord:
    try:
        return await service.get_config(
            workspace_id=workspace_id,
            config_id=config_id,
            include_deleted=include_deleted,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


@router.delete(
    "/configs/{config_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive or delete a configuration package",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def delete_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    purge: Annotated[
        bool,
        Query(description="Permanently delete the config when true."),
    ] = False,
) -> Response:
    try:
        if purge:
            await service.hard_delete_config(
                workspace_id=workspace_id,
                config_id=config_id,
            )
        else:
            await service.archive_config(
                workspace_id=workspace_id,
                config_id=config_id,
                actor_id=str(actor.id),
            )
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except ConfigDependentJobsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error(
                "dependent_jobs",
                "Config has dependent jobs and cannot be deleted permanently.",
                {"countsByVersion": exc.counts_by_version},
            ),
        ) from exc
    except ConfigInvariantViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error("invariant_violation", exc.message),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/configs/{config_id}/restore",
    dependencies=[Security(require_csrf)],
    response_model=ConfigRecord,
    status_code=status.HTTP_200_OK,
    summary="Restore an archived configuration package",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def restore_config(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigRecord:
    try:
        return await service.restore_config(
            workspace_id=workspace_id,
            config_id=config_id,
            actor_id=str(actor.id),
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


# ---------------------------------------------------------------------------
# Version endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/configs/{config_id}/versions",
    response_model=list[ConfigVersionRecord],
    status_code=status.HTTP_200_OK,
    summary="List versions for a configuration",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_versions(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    version_status: Annotated[
        str | None,
        Query(description="Filter versions by status (active|inactive)."),
    ] = None,
    include_deleted: Annotated[
        bool,
        Query(description="Include archived versions in the response."),
    ] = False,
) -> list[ConfigVersionRecord]:
    valid_statuses = {None, "active", "inactive"}
    if version_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_api_error("invalid_status", "Status must be 'active' or 'inactive'."),
        )
    try:
        return await service.list_versions(
            workspace_id=workspace_id,
            config_id=config_id,
            status=version_status,
            include_deleted=include_deleted,
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


@router.get(
    "/configs/{config_id}/versions/active",
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve the active configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_active_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigVersionRecord:
    try:
        return await service.get_active_version(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


@router.post(
    "/configs/{config_id}/versions",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def create_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigVersionCreateRequest = VERSION_CREATE_BODY,
    response: Response,
) -> ConfigVersionRecord:
    try:
        record = await service.create_version(
            workspace_id=workspace_id,
            config_id=config_id,
            payload=payload,
            actor_id=str(actor.id),
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except ConfigInvariantViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error("invariant_violation", exc.message),
        ) from exc
    response.headers["Location"] = (
        f"/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{record.config_version_id}"
    )
    return record


@router.post(
    "/configs/{config_id}/versions/{config_version_id}/clone",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def clone_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigVersionCreateRequest = CLONE_BODY,
    response: Response,
) -> ConfigVersionRecord:
    try:
        record = await service.clone_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            payload=payload,
            actor_id=str(actor.id),
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except ConfigInvariantViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error("invariant_violation", exc.message),
        ) from exc
    response.headers["Location"] = (
        f"/api/v1/workspaces/{workspace_id}/configs/{config_id}/versions/{record.config_version_id}"
    )
    return record


@router.get(
    "/configs/{config_id}/versions/{config_version_id}",
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve configuration version metadata",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    include_deleted: Annotated[
        bool,
        Query(description="Include archived version metadata."),
    ] = False,
) -> ConfigVersionRecord:
    try:
        return await service.get_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            include_deleted=include_deleted,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


@router.post(
    "/configs/{config_id}/versions/{config_version_id}/activate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_200_OK,
    summary="Activate a configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def activate_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigVersionRecord:
    try:
        return await service.activate_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            actor_id=str(actor.id),
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except ConfigVersionActivationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error("activation_failed", exc.message),
        ) from exc


@router.delete(
    "/configs/{config_id}/versions/{config_version_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive or delete a configuration version",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def delete_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    purge: Annotated[
        bool,
        Query(description="Permanently delete the version when true."),
    ] = False,
) -> Response:
    try:
        if purge:
            await service.hard_delete_version(
                workspace_id=workspace_id,
                config_id=config_id,
                config_version_id=config_version_id,
            )
        else:
            await service.archive_version(
                workspace_id=workspace_id,
                config_id=config_id,
                config_version_id=config_version_id,
                actor_id=str(actor.id),
            )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except ConfigVersionDependentJobsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error(
                "dependent_jobs",
                "Version has dependent jobs and cannot be deleted permanently.",
                {"count": exc.job_count},
            ),
        ) from exc
    except ConfigInvariantViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error("invariant_violation", exc.message),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/configs/{config_id}/versions/{config_version_id}/restore",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionRecord,
    status_code=status.HTTP_200_OK,
    summary="Restore an archived configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def restore_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigVersionRecord:
    try:
        return await service.restore_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


# ---------------------------------------------------------------------------
# File endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/configs/{config_id}/versions/{config_version_id}/scripts",
    response_model=list[ConfigScriptSummary],
    status_code=status.HTTP_200_OK,
    summary="List scripts within a configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_version_scripts(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigScriptSummary]:
    try:
        return await service.list_scripts(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


@router.get(
    "/configs/{config_id}/versions/{config_version_id}/scripts/{script_path:path}",
    response_model=ConfigScriptContent,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a configuration version script",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_version_script(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    script_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    response: Response,
) -> ConfigScriptContent:
    try:
        record = await service.get_script(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            path=script_path,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError, VersionFileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    response.headers["ETag"] = f'"{record.sha256}"'
    return record


@router.post(
    "/configs/{config_id}/versions/{config_version_id}/scripts",
    dependencies=[Security(require_csrf)],
    response_model=ConfigScriptContent,
    status_code=status.HTTP_201_CREATED,
    summary="Create a script in a configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def create_version_script(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigScriptCreateRequest = SCRIPT_CREATE_BODY,
    response: Response,
) -> ConfigScriptContent:
    try:
        record = await service.create_script(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            payload=payload,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except VersionFileConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_api_error("file_conflict", str(exc)),
        ) from exc
    response.headers["ETag"] = f'"{record.sha256}"'
    return record


@router.put(
    "/configs/{config_id}/versions/{config_version_id}/scripts/{script_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=ConfigScriptContent,
    status_code=status.HTTP_200_OK,
    summary="Update a configuration version script",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_412_PRECONDITION_FAILED: {"model": ErrorMessage},
    },
)
async def update_version_script(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    script_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigScriptUpdateRequest = SCRIPT_UPDATE_BODY,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    response: Response,
) -> ConfigScriptContent:
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=_api_error("missing_precondition", "If-Match header is required."),
        )
    try:
        record = await service.update_script(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            path=script_path,
            payload=payload,
            expected_sha=if_match.strip('"'),
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError, VersionFileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except VersionFileConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=_api_error("etag_mismatch", str(exc)),
        ) from exc
    response.headers["ETag"] = f'"{record.sha256}"'
    return record


@router.delete(
    "/configs/{config_id}/versions/{config_version_id}/scripts/{script_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a configuration version file",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def delete_version_script(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    script_path: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    try:
        await service.delete_script(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            path=script_path,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError, VersionFileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Manifest endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/configs/{config_id}/versions/{config_version_id}/manifest",
    response_model=ManifestResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve configuration version manifest",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_manifest(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    response: Response,
) -> ManifestResponse:
    try:
        manifest_response, etag = await service.get_manifest(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    response.headers["ETag"] = f'"{etag}"'
    return manifest_response


@router.patch(
    "/configs/{config_id}/versions/{config_version_id}/manifest",
    dependencies=[Security(require_csrf)],
    response_model=ManifestResponse,
    status_code=status.HTTP_200_OK,
    summary="Update configuration version manifest",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_412_PRECONDITION_FAILED: {"model": ErrorMessage},
    },
)
async def update_manifest(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ManifestPatchRequest = MANIFEST_UPDATE_BODY,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ManifestResponse:
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=_api_error("missing_precondition", "If-Match header is required."),
        )
    try:
        manifest_response, etag = await service.update_manifest(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            payload=payload,
            expected_etag=if_match.strip('"'),
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc
    except ManifestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_api_error("invalid_manifest", str(exc)),
        ) from exc
    except ConfigInvariantViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=_api_error("etag_mismatch", exc.message),
        ) from exc
    response.headers["ETag"] = f'"{etag}"'
    return manifest_response


# ---------------------------------------------------------------------------
# Validation & testing endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/configs/{config_id}/versions/{config_version_id}/validate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionValidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate a configuration version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def validate_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigVersionValidateResponse:
    try:
        return await service.validate_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


@router.post(
    "/configs/{config_id}/versions/{config_version_id}/test",
    dependencies=[Security(require_csrf)],
    response_model=ConfigVersionTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a configuration version test",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def test_version(
    workspace_id: Annotated[str, Path(min_length=1)],
    config_id: Annotated[str, Path(min_length=1)],
    config_version_id: Annotated[str, Path(min_length=1)],
    service: Annotated[ConfigService, Depends(get_config_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigVersionTestRequest = TEST_BODY,
) -> ConfigVersionTestResponse:
    try:
        return await service.test_version(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            payload=payload,
        )
    except (ConfigNotFoundError, ConfigVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_api_error("not_found", str(exc)),
        ) from exc


__all__ = ["router"]
