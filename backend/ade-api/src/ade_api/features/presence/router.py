from __future__ import annotations

from collections.abc import Callable
import re
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import anyio
from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ade_api.api.deps import SettingsDep
from ade_api.core.auth import AuthenticationError, authenticate_websocket
from ade_api.core.auth.principal import AuthenticatedPrincipal, AuthVia
from ade_api.core.http.dependencies import (
    get_api_key_authenticator_websocket,
    get_bearer_authenticator,
    get_cookie_authenticator,
    get_rbac_service,
)
from ade_api.db import get_session_factory
from ade_db.models import User
from ade_api.settings import Settings

from .registry import ChannelKey, PresenceParticipant, get_presence_registry

router = APIRouter(prefix="/workspaces/{workspaceId}/presence", tags=["presence"])

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
    if "*" in settings.server_cors_origins:
        return True
    if settings.server_cors_origin_regex:
        if re.match(settings.server_cors_origin_regex, normalized_origin):
            return True
    return normalized_origin in allowed


def _scope_permission(scope: str) -> str:
    base = scope.split(".", 1)[0]
    return _SCOPE_PERMISSIONS.get(base, "workspace.read")


def _authorize_scope(
    *,
    principal: AuthenticatedPrincipal,
    db: Session,
    workspace_id: WorkspacePath,
    scope: str,
) -> bool:
    permission_key = _scope_permission(scope)
    rbac = get_rbac_service(db)
    return rbac.has_permission(
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
    settings: SettingsDep,
) -> None:
    SessionLocal = get_session_factory(websocket)

    def _run_db_work(work: Callable[[Session], Any]) -> Any:
        with SessionLocal() as session:
            try:
                result = work(session)
                session.commit()
                return result
            except BaseException:
                session.rollback()
                raise

    def _authenticate(session: Session) -> tuple[AuthenticatedPrincipal, User | None]:
        api_keys = get_api_key_authenticator_websocket(session, settings)
        principal = authenticate_websocket(
            websocket,
            session,
            settings,
            api_keys,
            get_cookie_authenticator(session, settings),
            get_bearer_authenticator(session, settings),
        )
        user = session.get(User, principal.user_id)
        return principal, user

    try:
        principal, user = await anyio.to_thread.run_sync(_run_db_work, _authenticate)
    except AuthenticationError:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    if principal.auth_via == AuthVia.SESSION:
        if not _origin_allowed(websocket.headers.get("origin"), settings):
            await websocket.close(code=WS_CLOSE_FORBIDDEN)
            return

    if user is None:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    await websocket.accept()

    channel_key: ChannelKey | None = None
    client_id: str | None = None
    registry = get_presence_registry()

    last_seen = anyio.current_time()

    def touch() -> None:
        nonlocal last_seen
        last_seen = anyio.current_time()

    async def join_channel(scope: str, context: dict[str, Any]) -> None:
        nonlocal channel_key, client_id

        def _check_scope(session: Session) -> bool:
            return _authorize_scope(
                principal=principal,
                db=session,
                workspace_id=workspace_id,
                scope=scope,
            )

        allowed = await anyio.to_thread.run_sync(_run_db_work, _check_scope)
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

    async def sender() -> None:
        try:
            while True:
                await anyio.sleep(PRESENCE_TTL_SECONDS / 2)
                if anyio.current_time() - last_seen > PRESENCE_TTL_SECONDS:
                    await websocket.close(code=WS_CLOSE_TIMEOUT)
                    return
        except WebSocketDisconnect:
            return
        finally:
            tg.cancel_scope.cancel()

    async def receiver() -> None:
        nonlocal client_id
        try:
            try:
                with anyio.fail_after(HELLO_TIMEOUT_SECONDS):
                    raw = await websocket.receive_json()
            except TimeoutError:
                await websocket.close(code=WS_CLOSE_TIMEOUT)
                return
            except WebSocketDisconnect:
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
            try:
                await join_channel(scope, context)
            except RuntimeError:
                return
            touch()

            while True:
                try:
                    message = await websocket.receive_json()
                except WebSocketDisconnect:
                    return
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
                    try:
                        await join_channel(scope, context)
                    except RuntimeError:
                        return
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
        finally:
            tg.cancel_scope.cancel()

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(receiver)
            tg.start_soon(sender)
    finally:
        if channel_key and client_id:
            await registry.leave(channel_key=channel_key, client_id=client_id)
            await registry.broadcast(
                channel_key=channel_key,
                message={"type": "leave", "client_id": client_id},
                skip_client_id=client_id,
            )
