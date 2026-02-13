from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Security, status

from ade_api.api.deps import ReadSessionDep, WriteSessionDep
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    strict_cursor_query_guard,
)
from ade_api.core.http import require_authenticated, require_csrf
from ade_api.features.rbac.service import RbacService
from ade_db.models import User

from .schemas import InvitationCreate, InvitationLifecycleStatus, InvitationOut, InvitationPage
from .service import InvitationsService
from .sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(tags=["invitations"], dependencies=[Security(require_authenticated)])

InvitationPath = Annotated[
    UUID,
    Path(description="Invitation identifier", alias="invitationId"),
]

def _can_manage_invitation_scope(
    *,
    actor: User,
    rbac: RbacService,
    workspace_id: UUID | None,
) -> bool:
    if rbac.has_permission_for_user_id(
        user_id=actor.id,
        permission_key="invitations.manage_all",
        workspace_id=None,
    ):
        return True
    if rbac.has_permission_for_user_id(
        user_id=actor.id,
        permission_key="users.manage_all",
        workspace_id=None,
    ):
        return True
    if workspace_id is not None:
        if rbac.has_permission_for_user_id(
            user_id=actor.id,
            permission_key="workspace.invitations.manage",
            workspace_id=workspace_id,
        ):
            return True
        if rbac.has_permission_for_user_id(
            user_id=actor.id,
            permission_key="workspace.members.manage",
            workspace_id=workspace_id,
        ):
            return True
    return False


def _can_read_invitation_scope(
    *,
    actor: User,
    rbac: RbacService,
    workspace_id: UUID | None,
) -> bool:
    if rbac.has_permission_for_user_id(
        user_id=actor.id,
        permission_key="invitations.read_all",
        workspace_id=None,
    ):
        return True
    if rbac.has_permission_for_user_id(
        user_id=actor.id,
        permission_key="users.read_all",
        workspace_id=None,
    ):
        return True
    if workspace_id is not None:
        if rbac.has_permission_for_user_id(
            user_id=actor.id,
            permission_key="workspace.invitations.read",
            workspace_id=workspace_id,
        ):
            return True
        if rbac.has_permission_for_user_id(
            user_id=actor.id,
            permission_key="workspace.members.read",
            workspace_id=workspace_id,
        ):
            return True
    return False


@router.get(
    "/invitations",
    response_model=InvitationPage,
    response_model_exclude_none=True,
    summary="List invitations",
)
def list_invitations(
    actor: Annotated[User, Security(require_authenticated)],
    session: ReadSessionDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[
        None,
        Depends(strict_cursor_query_guard(allowed_extra={"workspace_id", "status"})),
    ],
    workspace_id: UUID | None = None,
    status_value: Annotated[InvitationLifecycleStatus | None, Query(alias="status")] = None,
) -> InvitationPage:
    rbac = RbacService(session=session)
    if not _can_read_invitation_scope(actor=actor, rbac=rbac, workspace_id=workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    service = InvitationsService(session=session)
    return service.list_invitations(
        workspace_id=workspace_id,
        status_value=status_value,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )


@router.post(
    "/invitations",
    dependencies=[Security(require_csrf)],
    response_model=InvitationOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create invitation",
)
def create_invitation(
    actor: Annotated[User, Security(require_authenticated)],
    session: WriteSessionDep,
    payload: InvitationCreate,
) -> InvitationOut:
    workspace_id = payload.workspace_context.workspace_id if payload.workspace_context else None
    rbac = RbacService(session=session)
    if not _can_manage_invitation_scope(actor=actor, rbac=rbac, workspace_id=workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    service = InvitationsService(session=session)
    return service.create_invitation(payload=payload, actor=actor)


@router.get(
    "/invitations/{invitationId}",
    response_model=InvitationOut,
    response_model_exclude_none=True,
    summary="Get invitation",
)
def get_invitation(
    actor: Annotated[User, Security(require_authenticated)],
    invitation_id: InvitationPath,
    session: ReadSessionDep,
) -> InvitationOut:
    service = InvitationsService(session=session)
    invitation = service.get_invitation(invitation_id=invitation_id)
    rbac = RbacService(session=session)
    if not _can_read_invitation_scope(
        actor=actor,
        rbac=rbac,
        workspace_id=invitation.workspace_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return service.serialize_invitation(invitation)


@router.post(
    "/invitations/{invitationId}/resend",
    dependencies=[Security(require_csrf)],
    response_model=InvitationOut,
    response_model_exclude_none=True,
    summary="Resend invitation",
)
def resend_invitation(
    actor: Annotated[User, Security(require_authenticated)],
    invitation_id: InvitationPath,
    session: WriteSessionDep,
) -> InvitationOut:
    service = InvitationsService(session=session)
    invitation = service.get_invitation(invitation_id=invitation_id)
    rbac = RbacService(session=session)
    if not _can_manage_invitation_scope(
        actor=actor,
        rbac=rbac,
        workspace_id=invitation.workspace_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return service.resend_invitation(invitation_id=invitation_id)


@router.post(
    "/invitations/{invitationId}/cancel",
    dependencies=[Security(require_csrf)],
    response_model=InvitationOut,
    response_model_exclude_none=True,
    summary="Cancel invitation",
)
def cancel_invitation(
    actor: Annotated[User, Security(require_authenticated)],
    invitation_id: InvitationPath,
    session: WriteSessionDep,
) -> InvitationOut:
    service = InvitationsService(session=session)
    invitation = service.get_invitation(invitation_id=invitation_id)
    rbac = RbacService(session=session)
    if not _can_manage_invitation_scope(
        actor=actor,
        rbac=rbac,
        workspace_id=invitation.workspace_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return service.cancel_invitation(invitation_id=invitation_id)


__all__ = ["router"]
