"""HTTP routes for configuration creation and validation."""

from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    Security,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse

from apps.api.app.shared.core.errors import ProblemDetail
from apps.api.app.shared.pagination import PageParams, paginate_sequence
from apps.api.app.shared.dependency import (
    get_configs_service,
    require_authenticated,
    require_csrf,
    require_workspace,
)

from ..users.models import User
from .etag import canonicalize_etag, format_etag, format_weak_etag
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
    ConfigurationPage,
    ConfigurationRecord,
    ConfigurationValidateResponse,
    FileListing,
    FileReadJson,
    FileRenameRequest,
    FileRenameResponse,
    FileWriteResponse,
)
from .service import (
    ConfigurationsService,
    DestinationExistsError,
    InvalidDepthError,
    InvalidPageTokenError,
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


def _problem(
    code: str,
    status_code: int,
    *,
    detail: str | None = None,
    title: str | None = None,
    meta: dict | None = None,
):
    payload = {
        "type": "about:blank",
        "title": title or code.replace("_", " ").title(),
        "status": status_code,
        "detail": detail,
        "code": code,
    }
    if meta:
        payload["meta"] = meta
    raise HTTPException(status_code, detail=payload)


def _accepts_json(request: Request, override: str | None) -> bool:
    if override == "json":
        return True
    accept = request.headers.get("accept") or ""
    return "application/json" in accept.lower()


def _parse_range_header(header_value: str, total_size: int) -> tuple[int, int]:
    if not header_value.lower().startswith("bytes="):
        raise ValueError("invalid-unit")
    value = header_value[6:]
    if "," in value:
        raise ValueError("multiple-ranges")
    start_str, end_str = value.split("-", 1)
    if not start_str and not end_str:
        raise ValueError("empty-range")
    if start_str:
        start = int(start_str)
        if start < 0 or start >= total_size:
            raise ValueError("start-out-of-range")
    else:
        length = int(end_str)
        if length <= 0:
            raise ValueError("invalid-length")
        start = max(total_size - length, 0)
        end = total_size - 1
        return start, end
    if end_str:
        end = int(end_str)
        if end < start:
            raise ValueError("end-before-start")
        end = min(end, total_size - 1)
    else:
        end = total_size - 1
    return start, end


@router.get(
    "/configurations",
    response_model=ConfigurationPage,
    response_model_exclude_none=True,
    summary="List configurations for a workspace",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
    },
)
async def list_configurations(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    page: Annotated[PageParams, Depends()],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> ConfigurationPage:
    records = await service.list_configurations(workspace_id=workspace_id)
    items = [ConfigurationRecord.model_validate(record) for record in records]
    page_result = paginate_sequence(
        items,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return ConfigurationPage(**page_result.model_dump())


@router.get(
    "/configurations/{config_id}",
    response_model=ConfigurationRecord,
    response_model_exclude_none=True,
    summary="Retrieve configuration metadata",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
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
    response_model=FileListing,
    response_model_exclude_none=True,
    summary="List editable files and directories",
)
async def list_config_files(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    prefix: str = "",
    depth: Literal["0", "1", "infinity"] = "infinity",
    include: Annotated[list[str] | None, Query(alias="include")] = None,
    exclude: Annotated[list[str] | None, Query(alias="exclude")] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    page_token: str | None = None,
    sort: Literal["path", "name", "mtime", "size"] = "path",
    order: Literal["asc", "desc"] = "asc",
) -> Response:
    try:
        listing = await service.list_files(
            workspace_id=workspace_id,
            config_id=config_id,
            prefix=prefix,
            depth=depth,
            include=include or [],
            exclude=exclude or [],
            limit=limit,
            page_token=page_token,
            sort=sort,
            order=order,
        )
    except ConfigurationNotFoundError:
        _problem("config_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidDepthError:
        _problem("invalid_depth", status.HTTP_400_BAD_REQUEST, detail="depth must be 0, 1, or infinity")
    except InvalidPageTokenError:
        _problem("invalid_page_token", status.HTTP_400_BAD_REQUEST, detail="page_token is invalid")

    weak_etag = format_weak_etag(listing["fileset_hash"])
    client_token = canonicalize_etag(request.headers.get("if-none-match"))
    headers = {}
    if weak_etag:
        headers["ETag"] = weak_etag
    if client_token and listing["fileset_hash"] and client_token == listing["fileset_hash"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    payload = FileListing.model_validate(listing)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


@router.post(
    "/configurations",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a configuration from a template or clone",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
        status.HTTP_409_CONFLICT: {"model": ProblemDetail},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ProblemDetail},
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
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
        status.HTTP_409_CONFLICT: {"model": ProblemDetail},
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
        status.HTTP_200_OK: {"content": {"application/octet-stream": {} }},
        status.HTTP_206_PARTIAL_CONTENT: {"content": {"application/octet-stream": {}}},
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
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
        _problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    try:
        info = await service.read_file(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=file_path,
            include_content=True,
        )
    except ConfigurationNotFoundError:
        _problem("config_not_found", status.HTTP_404_NOT_FOUND)
    except FileNotFoundError:
        _problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        _problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        _problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))

    canon_requested = canonicalize_etag(request.headers.get("if-none-match"))
    etag_canonical = info["etag"]
    etag_header = format_etag(etag_canonical) or ""
    headers = {"ETag": etag_header, "Last-Modified": info["mtime"].isoformat() if isinstance(info["mtime"], datetime) else str(info["mtime"])}

    if canon_requested and etag_canonical and canon_requested == etag_canonical:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    wants_json = _accepts_json(request, format)
    if wants_json:
        data = info["data"] or b""
        try:
            content = data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            content = base64.b64encode(data).decode("ascii")
            encoding = "base64"
        payload = FileReadJson(
            path=info["path"],
            encoding=encoding,
            content=content,
            size=info["size"],
            mtime=info["mtime"],
            etag=etag_canonical,
            content_type=info["content_type"],
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=payload.model_dump(mode="json"),
            headers=headers,
        )

    data = info["data"] or b""
    total_size = info["size"]
    range_header = request.headers.get("range")
    status_code = status.HTTP_200_OK
    if range_header:
        try:
            start, end = _parse_range_header(range_header, total_size)
        except ValueError:
            _problem(
                "range_not_satisfiable",
                status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Invalid Range header",
            )
        data = data[start : end + 1]
        headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT
    headers["Content-Length"] = str(len(data))
    headers["Accept-Ranges"] = "bytes"
    return Response(content=data, media_type=info["content_type"], headers=headers, status_code=status_code)


@router.head(
    "/configurations/{config_id}/files/{file_path:path}",
    responses={status.HTTP_200_OK: {"model": None}},
)
async def head_config_file(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    file_path: str,
    service: Annotated[ConfigurationsService, Depends(get_configs_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Configs.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    if not file_path:
        _problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    try:
        info = await service.read_file(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=file_path,
            include_content=False,
        )
    except ConfigurationNotFoundError:
        _problem("config_not_found", status.HTTP_404_NOT_FOUND)
    except FileNotFoundError:
        _problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        _problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        _problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))

    headers = {
        "ETag": format_etag(info["etag"]) or "",
        "Last-Modified": info["mtime"].isoformat() if isinstance(info["mtime"], datetime) else str(info["mtime"]),
        "Content-Type": info["content_type"],
        "Content-Length": str(info["size"]),
    }
    return Response(status_code=status.HTTP_200_OK, headers=headers)


@router.post(
    "/configurations/{config_id}/activate",
    dependencies=[Security(require_csrf)],
    response_model=ConfigurationRecord,
    summary="Activate a configuration",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
        status.HTTP_409_CONFLICT: {"model": ProblemDetail},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ProblemDetail},
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
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
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
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
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
    response_model=FileWriteResponse,
    responses={
        status.HTTP_200_OK: {"model": FileWriteResponse},
        status.HTTP_201_CREATED: {"model": FileWriteResponse},
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
        _problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
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
    except ConfigurationNotFoundError:
        _problem("config_not_found", status.HTTP_404_NOT_FOUND)
    except ConfigStateError as exc:
        _problem("config_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except FileNotFoundError:
        _problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        _problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        _problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PreconditionRequiredError:
        _problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        _problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    except PayloadTooLargeError as exc:
        _problem(
            "payload_too_large",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"payload exceeds {exc.limit} bytes",
        )

    payload = FileWriteResponse(
        path=result["path"],
        created=result.pop("created", False),
        size=result["size"],
        mtime=result["mtime"],
        etag=result["etag"],
    )
    headers = {"ETag": format_etag(result["etag"]) or ""}
    status_code = status.HTTP_201_CREATED if payload.created else status.HTTP_200_OK
    if payload.created:
        headers["Location"] = request.url.path
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


@router.delete(
    "/configurations/{config_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
        status.HTTP_409_CONFLICT: {"model": ProblemDetail},
        status.HTTP_412_PRECONDITION_FAILED: {"model": ProblemDetail},
        status.HTTP_428_PRECONDITION_REQUIRED: {"model": ProblemDetail},
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
        _problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    if_match = request.headers.get("if-match")
    try:
        await service.delete_file(
            workspace_id=workspace_id,
            config_id=config_id,
            relative_path=file_path,
            if_match=if_match,
        )
    except ConfigurationNotFoundError:
        _problem("config_not_found", status.HTTP_404_NOT_FOUND)
    except ConfigStateError as exc:
        _problem("config_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except FileNotFoundError:
        _problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        _problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        _problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PreconditionRequiredError:
        _problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        _problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/configurations/{config_id}/directories/{directory_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
        status.HTTP_409_CONFLICT: {"model": ProblemDetail},
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
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetail},
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetail},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetail},
        status.HTTP_409_CONFLICT: {"model": ProblemDetail},
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


@router.patch(
    "/configurations/{config_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=FileRenameResponse,
    summary="Rename or move a file",
)
async def rename_config_file(
    workspace_id: Annotated[str, Path(..., min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, Path(..., min_length=1, description="Configuration identifier")],
    file_path: str,
    payload: FileRenameRequest,
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
        _problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    if payload.op != "move":
        _problem("unsupported_operation", status.HTTP_400_BAD_REQUEST, detail="op must be 'move'")
    try:
        result = await service.rename_entry(
            workspace_id=workspace_id,
            config_id=config_id,
            source_path=file_path,
            dest_path=payload.to,
            overwrite=payload.overwrite,
            dest_if_match=payload.dest_if_match,
        )
    except ConfigurationNotFoundError:
        _problem("config_not_found", status.HTTP_404_NOT_FOUND)
    except FileNotFoundError:
        _problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        _problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        _problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ConfigStateError as exc:
        _problem("config_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except PreconditionRequiredError:
        _problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        _problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    except DestinationExistsError:
        _problem("dest_exists", status.HTTP_409_CONFLICT, detail="destination already exists")

    payload_model = FileRenameResponse(
        **result,
    )
    headers = {"ETag": format_etag(result["etag"]) or ""}
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload_model.model_dump(mode="json", by_alias=True),
        headers=headers,
    )


__all__ = ["router"]
