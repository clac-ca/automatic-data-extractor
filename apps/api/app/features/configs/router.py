"""HTTP routes for configuration creation and validation."""

from __future__ import annotations

import base64
import io
import json
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Request,
    Response,
    Security,
    status,
)
from fastapi.responses import StreamingResponse

from apps.api.app.shared.core.schema import ErrorMessage
from apps.api.app.shared.dependency import (
    get_configs_service,
    require_authenticated,
    require_csrf,
    require_workspace,
)

from ..users.models import User
from .etag import canonicalize_etag, format_etag
from .exceptions import (
    ConfigPublishConflictError,
    ConfigSourceInvalidError,
    ConfigSourceNotFoundError,
    ConfigStateError,
    ConfigStorageNotFoundError,
    ConfigurationNotFoundError,
    ConfigValidationFailedError,
)
from .schemas import (
    ConfigurationActivateRequest,
    ConfigurationCreate,
    ConfigurationRecord,
    ConfigurationValidateResponse,
)
from .service import (
    ConfigurationsService,
    InvalidPathError,
    PathNotAllowedError,
    PayloadTooLargeError,
    PreconditionFailedError,
    PreconditionRequiredError,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["configs"],
    dependencies=[Security(require_authenticated)],
)

CONFIG_CREATE_BODY = Body(
    ...,
    description="Display name and template/clone source for the configuration.",
)
ACTIVATE_BODY = Body(
    ConfigurationActivateRequest(),
    description="Activation options.",
)


@router.get(
    "/configurations",
    response_model=list[ConfigurationRecord],
    response_model_exclude_none=True,
    summary="List configurations for a workspace",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
    },
)
async def list_configurations(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> list[ConfigurationRecord]:
    records = await service.list_configurations(workspace_id=workspace_id)
    return [ConfigurationRecord.model_validate(record) for record in records]


@router.get(
    "/configurations/{config_id}",
    response_model=ConfigurationRecord,
    response_model_exclude_none=True,
    summary="Retrieve configuration metadata",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def read_configuration(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        record = await service.get_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="config_not_found"
        ) from exc
    return ConfigurationRecord.model_validate(record)


@router.get(
    "/configurations/{config_id}/files",
    summary="List editable files and directories",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def list_config_files(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> dict:
    try:
        entries = await service.list_files(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    return {"root": "", "entries": entries}


@router.post(
    "/configurations",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration from a template or clone",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorMessage},
    },
)
async def create_configuration(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigurationCreate = CONFIG_CREATE_BODY,
) -> ConfigurationRecord:
    try:
        record = await service.create_configuration(
            workspace_id=workspace_id,
            display_name=payload.display_name,
            source=payload.source,
        )
    except ConfigSourceNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="source_not_found",
        ) from exc
    except ConfigSourceInvalidError as exc:
        detail = {
            "error": "invalid_source_shape",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    except ConfigPublishConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="publish_conflict",
        ) from exc

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/{config_id}/validate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationValidateResponse,
    summary="Validate the configuration on disk",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def validate_configuration(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigurationValidateResponse:
    try:
        result = await service.validate_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="config_not_found"
        ) from exc
    except ConfigStorageNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="config_storage_missing"
        ) from exc

    payload = ConfigurationValidateResponse(
        workspace_id=workspace_id,
        config_id=config_id,
        status=result.configuration.status,
        content_digest=result.content_digest,
        issues=result.issues,
    )
    return payload


@router.get(
    "/configurations/{config_id}/files/{file_path:path}",
    responses={
        status.HTTP_200_OK: {"content": {"application/octet-stream": {}}},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_304_NOT_MODIFIED: {"model": None},
    },
)
async def read_config_file(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    file_path: str,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    format: str | None = None,
) -> Response:
    if not file_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="path_required")
    try:
        info = await service.read_file(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=file_path,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="file_not_found",
        ) from None
    except InvalidPathError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PathNotAllowedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    etag_header = format_etag(info["etag"]) or ""
    current = canonicalize_etag(request.headers.get("if-none-match"))
    if current and current == info["etag"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag_header})

    if format == "json":
        try:
            decoded = info["data"].decode("utf-8")
            encoding = "utf-8"
            content = decoded
        except UnicodeDecodeError:
            encoding = "base64"
            content = base64.b64encode(info["data"]).decode("ascii")
        return {
            "path": info["path"],
            "encoding": encoding,
            "content": content,
            "etag": etag_header,
            "size": info["size"],
            "mtime": info["mtime"],
        }

    return Response(
        content=info["data"],
        media_type=info["content_type"],
        headers={
            "ETag": etag_header,
            "Last-Modified": info["mtime"],
        },
    )


@router.post(
    "/configurations/{config_id}/activate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Activate a configuration",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorMessage},
    },
)
async def activate_configuration_endpoint(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    *,
    payload: ConfigurationActivateRequest = ACTIVATE_BODY,
) -> ConfigurationRecord:
    del payload  # ensure_build hook handled by future WPs
    try:
        record = await service.activate_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    except ConfigStorageNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="config_storage_missing",
        ) from exc
    except ConfigValidationFailedError as exc:
        detail = {
            "error": "validation_failed",
            "issues": [issue.model_dump() for issue in exc.issues],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ConfigurationRecord.model_validate(record)


@router.post(
    "/configurations/{config_id}/deactivate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Deactivate a configuration (was 'archive')",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def deactivate_configuration_endpoint(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigurationRecord:
    try:
        record = await service.deactivate_configuration(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    return ConfigurationRecord.model_validate(record)


@router.get(
    "/configurations/{config_id}/export",
    responses={
        status.HTTP_200_OK: {"content": {"application/zip": {}}},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
    },
)
async def export_config(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    format: str = "zip",
) -> StreamingResponse:
    if format != "zip":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="unsupported_format")
    try:
        blob = await service.export_zip(
            workspace_id=workspace_id,
            config_id=config_id,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    stream = io.BytesIO(blob)
    headers = {
        "Content-Disposition": f'attachment; filename="{config_id}.zip"',
    }
    return StreamingResponse(stream, media_type="application/zip", headers=headers)


@router.put(
    "/configurations/{config_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_200_OK: {"model": None},
        status.HTTP_201_CREATED: {"model": None},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
        status.HTTP_412_PRECONDITION_FAILED: {"model": ErrorMessage},
        status.HTTP_428_PRECONDITION_REQUIRED: {"model": ErrorMessage},
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": ErrorMessage},
    },
)
async def upsert_config_file(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    file_path: str,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    parents: bool = False,
) -> Response:
    if not file_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="path_required")
    data = await request.body()
    if_match = request.headers.get("if-match")
    if_none_match = request.headers.get("if-none-match")
    try:
        result = await service.write_file(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=file_path,
            content=data,
            parents=parents,
            if_match=if_match,
            if_none_match=if_none_match,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="file_not_found",
        ) from None
    except InvalidPathError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PathNotAllowedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PreconditionRequiredError:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED,
            detail="precondition_required",
        ) from None
    except PreconditionFailedError as exc:
        etag_header = format_etag(exc.current_etag)
        headers = {"ETag": etag_header} if etag_header else {}
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            detail="precondition_failed",
            headers=headers,
        ) from exc
    except PayloadTooLargeError as exc:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"payload exceeds {exc.limit} bytes",
        ) from exc

    etag_header = format_etag(result["etag"]) or ""
    body = {
        "path": result["path"],
        "size": result["size"],
        "mtime": result["mtime"],
        "etag": etag_header,
    }
    status_code = status.HTTP_201_CREATED if result.pop("created", False) else status.HTTP_200_OK
    payload = json.dumps(body).encode("utf-8")
    return Response(
        status_code=status_code,
        content=payload,
        media_type="application/json",
        headers={"ETag": etag_header},
    )


@router.delete(
    "/configurations/{config_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
        status.HTTP_412_PRECONDITION_FAILED: {"model": ErrorMessage},
        status.HTTP_428_PRECONDITION_REQUIRED: {"model": ErrorMessage},
    },
)
async def delete_config_file(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    file_path: str,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    if not file_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="path_required")
    if_match = request.headers.get("if-match")
    try:
        await service.delete_file(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=file_path,
            if_match=if_match,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="file_not_found",
        ) from None
    except InvalidPathError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PathNotAllowedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PreconditionRequiredError:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED,
            detail="precondition_required",
        ) from None
    except PreconditionFailedError as exc:
        etag_header = format_etag(exc.current_etag)
        headers = {"ETag": etag_header} if etag_header else {}
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            detail="precondition_failed",
            headers=headers,
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/configurations/{config_id}/directories/{directory_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def create_config_directory(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    directory_path: str,
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> dict:
    if not directory_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="path_required")
    try:
        await service.create_directory(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=directory_path,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidPathError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PathNotAllowedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"path": directory_path}


@router.delete(
    "/configurations/{config_id}/directories/{directory_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorMessage},
        status.HTTP_403_FORBIDDEN: {"model": ErrorMessage},
        status.HTTP_404_NOT_FOUND: {"model": ErrorMessage},
        status.HTTP_409_CONFLICT: {"model": ErrorMessage},
    },
)
async def delete_config_directory(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    directory_path: str,
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    recursive: bool = False,
) -> Response:
    if not directory_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="path_required")
    try:
        await service.delete_directory(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=directory_path,
            recursive=recursive,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="config_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="directory_not_found") from None
    except InvalidPathError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PathNotAllowedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
