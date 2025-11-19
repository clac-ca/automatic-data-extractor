"""HTTP routes for build orchestration and streaming."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Security, status
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse

from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.session import get_sessionmaker
from ade_api.shared.dependency import (
    get_builds_service,
    require_authenticated,
    require_csrf,
    require_workspace,
)

from .exceptions import BuildAlreadyInProgressError, BuildExecutionError, BuildNotFoundError
from .schemas import BuildCreateOptions, BuildCreateRequest, BuildLogsResponse, BuildResource
from .service import DEFAULT_STREAM_LIMIT, BuildExecutionContext, BuildsService

router = APIRouter(tags=["builds"], dependencies=[Security(require_authenticated)])
builds_service_dependency = Depends(get_builds_service)


def _event_bytes(event: Any) -> bytes:
    if hasattr(event, "json_bytes"):
        return event.json_bytes() + b"\n"
    return json.dumps(event).encode("utf-8") + b"\n"


async def _execute_build_background(
    context_data: dict[str, Any],
    options_data: dict[str, Any],
    settings_payload: dict[str, Any],
    storage_payload: dict[str, str],
) -> None:
    from ade_api.features.configs.storage import ConfigStorage
    from ade_api.settings import Settings

    settings = Settings(**settings_payload)
    session_factory = get_sessionmaker(settings=settings)
    storage = ConfigStorage(
        templates_root=Path(storage_payload["templates_root"]),
        configs_root=Path(storage_payload["configs_root"]),
    )
    context = BuildExecutionContext.from_dict(context_data)
    options = BuildCreateOptions(**options_data)
    async with session_factory() as session:
        service = BuildsService(
            session=session,
            settings=settings,
            storage=storage,
        )
        try:
            await service.run_to_completion(context=context, options=options)
        except Exception:  # pragma: no cover - defensive logging
            import logging

            logger = logging.getLogger(__name__)
            logger.exception(
                "Background build execution failed",
                extra={"build_id": context.build_id},
            )


@router.post(
    "/workspaces/{workspace_id}/configs/{config_id}/builds",
    response_model=BuildResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_build_endpoint(
    *,
    workspace_id: Annotated[str, PathParam(min_length=1, description="Workspace identifier")],
    config_id: Annotated[str, PathParam(min_length=1, description="Configuration identifier")],
    payload: BuildCreateRequest,
    background_tasks: BackgroundTasks,
    _actor: Annotated[
        object,
        Security(
            require_workspace("Workspace.Configs.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    service: BuildsService = builds_service_dependency,
) -> BuildResource | StreamingResponse:
    try:
        build, context = await service.prepare_build(
            workspace_id=workspace_id,
            config_id=config_id,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BuildAlreadyInProgressError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    resource = service.to_resource(build)
    if not payload.stream:
        storage_payload = {
            "templates_root": str(service.storage.templates_root),
            "configs_root": str(service.storage.configs_root),
        }
        background_tasks.add_task(
            _execute_build_background,
            context.as_dict(),
            payload.options.model_dump(),
            service.settings.model_dump(mode="python"),
            storage_payload,
        )
        return resource

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for event in service.stream_build(context=context, options=payload.options):
                yield _event_bytes(event)
        except BuildNotFoundError:
            return
        except BuildExecutionError as exc:
            error_event = {
                "object": "ade.build.event",
                "type": "build.log",
                "build_id": build.id,
                "created": int(utc_now().timestamp()),
                "stream": "stderr",
                "message": str(exc),
            }
            yield _event_bytes(error_event)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.get("/builds/{build_id}", response_model=BuildResource)
async def get_build_endpoint(
    build_id: Annotated[str, PathParam(min_length=1, description="Build identifier")],
    service: BuildsService = builds_service_dependency,
) -> BuildResource:
    build = await service.get_build(build_id)
    if build is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Build not found")
    return service.to_resource(build)


@router.get("/builds/{build_id}/logs", response_model=BuildLogsResponse)
async def get_build_logs_endpoint(
    build_id: Annotated[str, PathParam(min_length=1, description="Build identifier")],
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=DEFAULT_STREAM_LIMIT, ge=1, le=DEFAULT_STREAM_LIMIT),
    service: BuildsService = builds_service_dependency,
) -> BuildLogsResponse:
    build = await service.get_build(build_id)
    if build is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Build not found")
    return await service.get_logs(build_id=build_id, after_id=after_id, limit=limit)
