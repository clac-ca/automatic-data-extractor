"""HTTP routes for browsing and editing configuration files."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, Security, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ade_api.api.deps import get_configurations_service
from ade_api.core.http import require_csrf, require_workspace
from ade_api.models import User

from ..etag import canonicalize_etag, format_etag, format_weak_etag
from ..exceptions import (
    ConfigStateError,
    ConfigurationNotFoundError,
)
from ..http import ConfigurationIdPath, WorkspaceIdPath, raise_problem
from ..schemas import (
    DirectoryWriteResponse,
    FileListing,
    FileReadJson,
    FileRenameRequest,
    FileRenameResponse,
    FileWriteResponse,
)
from ..service import (
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

router = APIRouter()


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


def _upsert_response(
    payload: BaseModel,
    *,
    created: bool,
    request: Request,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = dict(headers or {})
    if created:
        response_headers.setdefault("Location", str(request.url.path))
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=response_headers,
    )


@router.get(
    "/configurations/{configuration_id}/files",
    response_model=FileListing,
    response_model_exclude_none=True,
    summary="List editable files and directories",
)
async def list_config_files(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
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
            configuration_id=configuration_id,
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
        raise_problem("configuration_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidDepthError:
        raise_problem(
            "invalid_depth",
            status.HTTP_400_BAD_REQUEST,
            detail="depth must be 0, 1, or infinity",
        )
    except InvalidPageTokenError:
        raise_problem(
            "invalid_page_token",
            status.HTTP_400_BAD_REQUEST,
            detail="page_token is invalid",
        )

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


@router.get(
    "/configurations/{configuration_id}/files/{file_path:path}",
    responses={
        status.HTTP_200_OK: {"content": {"application/octet-stream": {}}},
        status.HTTP_206_PARTIAL_CONTENT: {"content": {"application/octet-stream": {}}},
        status.HTTP_304_NOT_MODIFIED: {"model": None},
    },
)
async def read_config_file(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    file_path: str,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspace_id}"],
        ),
    ],
    format: str | None = None,
) -> Response:
    if not file_path:
        raise_problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    try:
        info = await service.read_file(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            relative_path=file_path,
            include_content=True,
        )
    except ConfigurationNotFoundError:
        raise_problem("configuration_not_found", status.HTTP_404_NOT_FOUND)
    except FileNotFoundError:
        raise_problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        raise_problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        raise_problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))

    canon_requested = canonicalize_etag(request.headers.get("if-none-match"))
    etag_canonical = info["etag"]
    etag_header = format_etag(etag_canonical) or ""
    headers = {
        "ETag": etag_header,
        "Last-Modified": (
            info["mtime"].isoformat() if isinstance(info["mtime"], datetime) else str(info["mtime"])
        ),
    }

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
            raise_problem(
                "range_not_satisfiable",
                status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Invalid Range header",
            )
        data = data[start : end + 1]
        headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT
    headers["Content-Length"] = str(len(data))
    headers["Accept-Ranges"] = "bytes"
    return Response(
        content=data,
        media_type=info["content_type"],
        headers=headers,
        status_code=status_code,
    )


@router.head(
    "/configurations/{configuration_id}/files/{file_path:path}",
    responses={status.HTTP_200_OK: {"model": None}},
)
async def head_config_file(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    file_path: str,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    if not file_path:
        raise_problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    try:
        info = await service.read_file(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            relative_path=file_path,
            include_content=False,
        )
    except ConfigurationNotFoundError:
        raise_problem("configuration_not_found", status.HTTP_404_NOT_FOUND)
    except FileNotFoundError:
        raise_problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        raise_problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        raise_problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))

    headers = {
        "ETag": format_etag(info["etag"]) or "",
        "Last-Modified": (
            info["mtime"].isoformat() if isinstance(info["mtime"], datetime) else str(info["mtime"])
        ),
        "Content-Type": info["content_type"],
        "Content-Length": str(info["size"]),
    }
    return Response(status_code=status.HTTP_200_OK, headers=headers)


@router.put(
    "/configurations/{configuration_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=FileWriteResponse,
    responses={
        status.HTTP_200_OK: {"model": FileWriteResponse},
        status.HTTP_201_CREATED: {"model": FileWriteResponse},
    },
)
async def upsert_config_file(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    file_path: str,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
    parents: bool = False,
) -> Response:
    if not file_path:
        raise_problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    data = await request.body()
    if_match = request.headers.get("if-match")
    if_none_match = request.headers.get("if-none-match")
    try:
        result = await service.write_file(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            relative_path=file_path,
            content=data,
            parents=parents,
            if_match=if_match,
            if_none_match=if_none_match,
        )
    except ConfigurationNotFoundError:
        raise_problem("configuration_not_found", status.HTTP_404_NOT_FOUND)
    except ConfigStateError as exc:
        raise_problem("configuration_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except FileNotFoundError:
        raise_problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        raise_problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        raise_problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PreconditionRequiredError:
        raise_problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        raise_problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    except PayloadTooLargeError as exc:
        raise_problem(
            "payload_too_large",
            status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"payload exceeds {exc.limit} bytes",
        )

    payload = FileWriteResponse(
        path=result["path"],
        created=result.pop("created", False),
        size=result["size"],
        mtime=result["mtime"],
        etag=result["etag"],
    )
    return _upsert_response(
        payload,
        created=payload.created,
        request=request,
        headers={"ETag": format_etag(result["etag"]) or ""},
    )


@router.delete(
    "/configurations/{configuration_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_config_file(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    file_path: str,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    if not file_path:
        raise_problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    if_match = request.headers.get("if-match")
    try:
        await service.delete_file(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            relative_path=file_path,
            if_match=if_match,
        )
    except ConfigurationNotFoundError:
        raise_problem("configuration_not_found", status.HTTP_404_NOT_FOUND)
    except ConfigStateError as exc:
        raise_problem("configuration_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except FileNotFoundError:
        raise_problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        raise_problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        raise_problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PreconditionRequiredError:
        raise_problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        raise_problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/configurations/{configuration_id}/directories/{directory_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=DirectoryWriteResponse,
    responses={
        status.HTTP_200_OK: {
            "model": DirectoryWriteResponse,
            "description": "Directory already exists",
        },
        status.HTTP_201_CREATED: {
            "model": DirectoryWriteResponse,
            "description": "Directory created",
        },
    },
)
async def create_config_directory(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    directory_path: str,
    request: Request,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    if not directory_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="path_required")
    try:
        _, created = await service.create_directory(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            relative_path=directory_path,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
    except ConfigStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidPathError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PathNotAllowedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    payload = DirectoryWriteResponse(path=directory_path, created=created)
    return _upsert_response(payload, created=payload.created, request=request)


@router.delete(
    "/configurations/{configuration_id}/directories/{directory_path:path}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_config_directory(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    directory_path: str,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
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
            configuration_id=configuration_id,
            relative_path=directory_path,
            recursive=recursive,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="configuration_not_found") from exc
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
    "/configurations/{configuration_id}/files/{file_path:path}",
    dependencies=[Security(require_csrf)],
    response_model=FileRenameResponse,
    summary="Rename or move a file",
)
async def rename_config_file(
    workspace_id: WorkspaceIdPath,
    configuration_id: ConfigurationIdPath,
    file_path: str,
    payload: FileRenameRequest,
    service: Annotated[ConfigurationsService, Depends(get_configurations_service)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> Response:
    if not file_path:
        raise_problem("path_required", status.HTTP_400_BAD_REQUEST, detail="file_path is required")
    if payload.op != "move":
        raise_problem(
            "unsupported_operation",
            status.HTTP_400_BAD_REQUEST,
            detail="op must be 'move'",
        )
    try:
        result = await service.rename_entry(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            source_path=file_path,
            dest_path=payload.to,
            overwrite=payload.overwrite,
            dest_if_match=payload.dest_if_match,
        )
    except ConfigurationNotFoundError:
        raise_problem("configuration_not_found", status.HTTP_404_NOT_FOUND)
    except FileNotFoundError:
        raise_problem("file_not_found", status.HTTP_404_NOT_FOUND)
    except InvalidPathError as exc:
        raise_problem("invalid_path", status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PathNotAllowedError as exc:
        raise_problem("path_not_allowed", status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ConfigStateError as exc:
        raise_problem("configuration_not_editable", status.HTTP_409_CONFLICT, detail=str(exc))
    except PreconditionRequiredError:
        raise_problem("precondition_required", status.HTTP_428_PRECONDITION_REQUIRED)
    except PreconditionFailedError as exc:
        raise_problem(
            "precondition_failed",
            status.HTTP_412_PRECONDITION_FAILED,
            meta={"current_etag": format_etag(exc.current_etag)},
        )
    except DestinationExistsError:
        raise_problem("dest_exists", status.HTTP_409_CONFLICT, detail="destination already exists")

    payload_model = FileRenameResponse(
        **result,
    )
    headers = {"ETag": format_etag(result["etag"]) or ""}
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload_model.model_dump(mode="json", by_alias=True),
        headers=headers,
    )
