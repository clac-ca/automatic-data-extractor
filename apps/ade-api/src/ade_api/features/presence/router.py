from __future__ import annotations

import asyncio
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Path, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.auth import AuthenticationError, authenticate_websocket
from ade_api.core.auth.principal import AuthenticatedPrincipal, AuthVia
from ade_api.core.http.dependencies import (
    get_api_key_authenticator_websocket,
    get_bearer_authenticator,
    get_cookie_authenticator,
    get_rbac_service,
)
from ade_api.db import get_db_session
from ade_api.models import User
from ade_api.settings import Settings, get_settings

from .registry import ChannelKey, PresenceParticipant, get_presence_registry

router = APIRouter(prefix="/workspaces/{workspaceId}/presence", tags=["presence"])

WebSocketSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]

PRESENCE_TTL_SECONDS = 60
PRESENCE_HEARTBEAT_SECONDS = 15
HELLO_TIMEOUT_SECONDS = 10

WS_CLOSE_BAD_REQUEST = 4400
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_TIMEOUT = 4408

_SCOPE_PERMISSIONS = {
    "documents": "workspace.documents.read",
    "configs": "workspace.configurations.read",
    "configurations": "workspace.configurations.read",
    "runs": "workspace.runs.read",
}


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


def _scope_permission(scope: str) -> str:
    base = scope.split(".", 1)[0]
    return _SCOPE_PERMISSIONS.get(base, "workspace.read")


async def _authorize_scope(
    *,
    principal: AuthenticatedPrincipal,
    db: AsyncSession,
    workspace_id: WorkspacePath,
    scope: str,
) -> bool:
    permission_key = _scope_permission(scope)
    rbac = get_rbac_service(db)
    return await rbac.has_permission(
        principal=principal,
        permission_key=permission_key,
        workspace_id=workspace_id,
    )


def _parse_hello(payload: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    scope = str(payload.get("scope") or "").strip()
    if not scope:
        raise ValueError("Presence scope is required")
    raw_context = payload.get("context")
    if raw_context is None:
        context: dict[str, Any] = {}
    elif isinstance(raw_context, dict):
        context = raw_context
    else:
        raise ValueError("Presence context must be an object")
    client_id = payload.get("client_id")
    if client_id is not None:
        client_id = str(client_id).strip() or None
    return scope, context, client_id


@router.websocket("")
async def presence_ws(
    websocket: WebSocket,
    workspace_id: WorkspacePath,
    db: WebSocketSessionDep,
    settings: SettingsDep,
    api_keys=Depends(get_api_key_authenticator_websocket),
) -> None:
    try:
        principal = await authenticate_websocket(
            websocket,
            db,
            settings,
            api_keys,
            get_cookie_authenticator(db, settings),
            get_bearer_authenticator(db, settings),
        )
    except AuthenticationError:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    if principal.auth_via == AuthVia.SESSION:
        if not _origin_allowed(websocket.headers.get("origin"), settings):
            await websocket.close(code=WS_CLOSE_FORBIDDEN)
            return

    user = await db.get(User, principal.user_id)
    if user is None:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    await websocket.accept()

    channel_key: ChannelKey | None = None
    client_id: str | None = None
    registry = get_presence_registry()

    loop = asyncio.get_running_loop()
    last_seen = loop.time()

    def touch() -> None:
        nonlocal last_seen
        last_seen = loop.time()

    async def monitor_timeout() -> None:
        while True:
            await asyncio.sleep(PRESENCE_TTL_SECONDS / 2)
            if loop.time() - last_seen > PRESENCE_TTL_SECONDS:
                await websocket.close(code=WS_CLOSE_TIMEOUT)
                break

    async def join_channel(scope: str, context: dict[str, Any]) -> None:
        nonlocal channel_key, client_id

        allowed = await _authorize_scope(
            principal=principal,
            db=db,
            workspace_id=workspace_id,
            scope=scope,
        )
        if not allowed:
            await websocket.close(code=WS_CLOSE_FORBIDDEN)
            raise RuntimeError("presence.forbidden")

        if client_id is None:
            client_id = str(uuid4())

        if channel_key is not None:
            await registry.leave(channel_key=channel_key, client_id=client_id)
            await registry.broadcast(
                channel_key=channel_key,
                message={"type": "leave", "client_id": client_id},
                skip_client_id=client_id,
            )

        participant = PresenceParticipant(
            client_id=client_id,
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            status="active",
            scope=scope,
            context=context,
        )
        channel_key, snapshot = await registry.join(
            workspace_id=workspace_id,
            participant=participant,
            websocket=websocket,
        )
        await websocket.send_json(
            {
                "type": "hello",
                "client_id": client_id,
                "heartbeat_interval": PRESENCE_HEARTBEAT_SECONDS,
                "ttl_seconds": PRESENCE_TTL_SECONDS,
            }
        )
        await websocket.send_json(
            {
                "type": "snapshot",
                "scope": scope,
                "context": context,
                "participants": snapshot,
            }
        )
        await registry.broadcast(
            channel_key=channel_key,
            message={"type": "join", "participant": participant.to_public()},
            skip_client_id=client_id,
        )

    timeout_task = asyncio.create_task(monitor_timeout())

    try:
        try:
            raw = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=HELLO_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            await websocket.close(code=WS_CLOSE_TIMEOUT)
            return
        except ValueError:
            await websocket.close(code=WS_CLOSE_BAD_REQUEST)
            return
        if not isinstance(raw, dict) or raw.get("type") != "hello":
            await websocket.close(code=WS_CLOSE_BAD_REQUEST)
            return

        scope, context, hello_client_id = _parse_hello(raw)
        if hello_client_id and client_id is None:
            client_id = hello_client_id
        await join_channel(scope, context)
        touch()

        while True:
            try:
                message = await websocket.receive_json()
            except ValueError:
                await websocket.close(code=WS_CLOSE_BAD_REQUEST)
                return
            if not isinstance(message, dict):
                await websocket.close(code=WS_CLOSE_BAD_REQUEST)
                return

            message_type = message.get("type")
            if not isinstance(message_type, str):
                continue

            message_type = message_type.strip()
            if not message_type:
                continue

            if message_type == "heartbeat":
                touch()
                continue

            if message_type == "hello":
                scope, context, hello_client_id = _parse_hello(message)
                if hello_client_id and client_id is None:
                    client_id = hello_client_id
                await join_channel(scope, context)
                touch()
                continue

            if message_type in {"presence", "selection", "editing"}:
                if channel_key is None or client_id is None:
                    continue
                payload = {key: value for key, value in message.items() if key != "type"}
                await registry.update(
                    channel_key=channel_key,
                    client_id=client_id,
                    update_type=message_type,
                    payload=payload,
                )
                await registry.broadcast(
                    channel_key=channel_key,
                    message={
                        "type": message_type,
                        "client_id": client_id,
                        **payload,
                    },
                    skip_client_id=client_id,
                )
                touch()
    except WebSocketDisconnect:
        pass
    except RuntimeError:
        # join_channel may raise after closing on forbidden access
        pass
    finally:
        if channel_key and client_id:
            await registry.leave(channel_key=channel_key, client_id=client_id)
            await registry.broadcast(
                channel_key=channel_key,
                message={"type": "leave", "client_id": client_id},
                skip_client_id=client_id,
            )
        timeout_task.cancel()
