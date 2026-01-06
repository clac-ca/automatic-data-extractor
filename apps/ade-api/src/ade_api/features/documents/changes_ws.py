from __future__ import annotations

import asyncio
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Path, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.auth import AuthenticationError, authenticate_websocket
from ade_api.core.auth.principal import AuthVia
from ade_api.core.http.dependencies import (
    get_api_key_authenticator_websocket,
    get_bearer_authenticator,
    get_cookie_authenticator,
    get_rbac_service,
)
from ade_api.db import db as database, get_db_session
from ade_api.settings import Settings, get_settings

from .change_feed import DocumentChangeCursorTooOld
from .changes_realtime import get_documents_changes_hub
from .service import DocumentsService

ws_router = APIRouter(prefix="/workspaces/{workspaceId}/documents/changes", tags=["documents"])

WebSocketSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]

WS_CLOSE_BAD_REQUEST = 4400
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_TIMEOUT = 4408
WS_CLOSE_RESYNC_REQUIRED = 4409

HELLO_TIMEOUT_SECONDS = 10
CATCHUP_LIMIT = 200


def _normalize_origin(origin: str) -> str:
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _origin_allowed(origin: str | None, settings: Settings) -> bool:
    if not origin:
        return False
    if "*" in settings.server_cors_origins:
        return True

    allowed: set[str] = set()
    for candidate in settings.server_cors_origins:
        normalized = _normalize_origin(candidate)
        if normalized:
            allowed.add(normalized)

    for candidate in (settings.frontend_url, settings.server_public_url):
        if not candidate:
            continue
        normalized = _normalize_origin(candidate)
        if normalized:
            allowed.add(normalized)

    normalized_origin = _normalize_origin(origin)
    if not normalized_origin:
        return False
    return normalized_origin in allowed


async def _send_catchup(
    *,
    service: DocumentsService,
    subscriber,
    workspace_id: UUID,
    start_cursor: int,
    watermark: int,
) -> None:
    cursor = start_cursor
    if cursor >= watermark:
        message = {
            "type": "changes",
            "workspaceId": str(workspace_id),
            "fromCursor": str(cursor),
            "toCursor": str(watermark),
            "nextCursor": str(watermark),
            "items": [],
        }
        if not await subscriber.send(message):
            raise WebSocketDisconnect()
        return

    while True:
        page = await service.list_document_changes(
            workspace_id=workspace_id,
            cursor_token=str(cursor),
            limit=CATCHUP_LIMIT,
            max_cursor=watermark,
        )
        message = {
            "type": "changes",
            "workspaceId": str(workspace_id),
            "fromCursor": str(cursor),
            "toCursor": str(watermark),
            "nextCursor": page.next_cursor,
            "items": [item.model_dump(by_alias=True, exclude_none=True) for item in page.items],
        }
        if not await subscriber.send(message):
            raise WebSocketDisconnect()

        next_cursor = int(page.next_cursor)
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if cursor >= watermark:
            break


@ws_router.websocket("/ws")
async def documents_changes_ws(
    websocket: WebSocket,
    workspace_id: WorkspacePath,
    db_session: WebSocketSessionDep,
    settings: SettingsDep,
    api_keys=Depends(get_api_key_authenticator_websocket),
) -> None:
    try:
        principal = await authenticate_websocket(
            websocket,
            db_session,
            settings,
            api_keys,
            get_cookie_authenticator(db_session, settings),
            get_bearer_authenticator(db_session, settings),
        )
    except AuthenticationError:
        await db_session.close()
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    if principal.auth_via == AuthVia.SESSION:
        if not _origin_allowed(websocket.headers.get("origin"), settings):
            await db_session.close()
            await websocket.close(code=WS_CLOSE_FORBIDDEN)
            return

    rbac = get_rbac_service(db_session)
    allowed = await rbac.has_permission(
        principal=principal,
        permission_key="workspace.documents.read",
        workspace_id=workspace_id,
    )
    await db_session.close()
    if not allowed:
        await websocket.close(code=WS_CLOSE_FORBIDDEN)
        return

    await websocket.accept()

    try:
        payload = await asyncio.wait_for(websocket.receive_json(), timeout=HELLO_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await websocket.close(code=WS_CLOSE_TIMEOUT)
        return
    except Exception:
        await websocket.close(code=WS_CLOSE_BAD_REQUEST)
        return

    if not isinstance(payload, dict) or payload.get("type") != "subscribe":
        await websocket.close(code=WS_CLOSE_BAD_REQUEST)
        return

    if payload.get("workspaceId") and str(payload.get("workspaceId")) != str(workspace_id):
        await websocket.close(code=WS_CLOSE_BAD_REQUEST)
        return

    cursor_token = payload.get("cursor")
    if not isinstance(cursor_token, str):
        await websocket.close(code=WS_CLOSE_BAD_REQUEST)
        return

    try:
        cursor = int(cursor_token)
    except ValueError:
        await websocket.close(code=WS_CLOSE_BAD_REQUEST)
        return

    hub = get_documents_changes_hub(
        settings=settings,
        close_code_resync=WS_CLOSE_RESYNC_REQUIRED,
    )
    subscriber = await hub.register(workspace_id=workspace_id, websocket=websocket)

    try:
        async with database.sessionmaker() as session:
            service = DocumentsService(session=session, settings=settings)
            watermark = await service._changes.current_cursor(workspace_id=workspace_id)
            await hub.registry.set_stream_start_cursor(
                workspace_id=workspace_id,
                client_id=subscriber.client_id,
                cursor=watermark,
            )

            await _send_catchup(
                service=service,
                subscriber=subscriber,
                workspace_id=workspace_id,
                start_cursor=cursor,
                watermark=watermark,
            )

        await hub.registry.mark_ready(
            workspace_id=workspace_id,
            client_id=subscriber.client_id,
        )
    except WebSocketDisconnect:
        await hub.unregister(workspace_id=workspace_id, client_id=subscriber.client_id)
        return
    except DocumentChangeCursorTooOld as exc:
        await hub.registry.send_resync(
            subscriber=subscriber,
            latest_cursor=exc.latest_cursor,
            close_code=WS_CLOSE_RESYNC_REQUIRED,
        )
        return
    except Exception:
        await subscriber.close(code=WS_CLOSE_BAD_REQUEST)
        await hub.unregister(workspace_id=workspace_id, client_id=subscriber.client_id)
        return

    try:
        while True:
            message: Any = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            if message.get("type") == "heartbeat":
                continue
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unregister(workspace_id=workspace_id, client_id=subscriber.client_id)


__all__ = ["ws_router"]
