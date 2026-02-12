from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Security, status

from ade_api.api.deps import ReadSessionDep, WriteSessionDep
from ade_api.core.http import require_authenticated, require_csrf
from ade_api.features.rbac.service import RbacService
from ade_db.models import InvitationStatus, User

from .schemas import InvitationCreate, InvitationListResponse, InvitationOut
from .service import InvitationsService

router = APIRouter(tags=["invitations"], dependencies=[Security(require_authenticated)])

InvitationPath = Annotated[
    UUID,
    Path(description="Invitation identifier", alias="invitationId"),
]


def _workspace_id_from_metadata(metadata: dict[str, object]) -> tuple[UUID | None, bool]:
    workspace_raw = metadata.get("workspaceId")
    if workspace_raw is None:
        return None, False
    if not isinstance(workspace_raw, str):
        return None, True
    try:
        return UUID(workspace_raw), False
    except (TypeError, ValueError):
        return None, True


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
    response_model=InvitationListResponse,
    response_model_exclude_none=True,
    summary="List invitations",
)
def list_invitations(
    actor: Annotated[User, Security(require_authenticated)],
    session: ReadSessionDep,
    workspace_id: UUID | None = None,
    invitation_status: InvitationStatus | None = None,
) -> InvitationListResponse:
    rbac = RbacService(session=session)
    if not _can_read_invitation_scope(actor=actor, rbac=rbac, workspace_id=workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    service = InvitationsService(session=session)
    return service.list_invitations(workspace_id=workspace_id, status_value=invitation_status)


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
    metadata = invitation.metadata_payload or {}
    workspace_id, invalid_workspace_scope = _workspace_id_from_metadata(metadata)
    rbac = RbacService(session=session)
    if invalid_workspace_scope or not _can_read_invitation_scope(
        actor=actor,
        rbac=rbac,
        workspace_id=workspace_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return service.get_invitation_out(invitation_id=invitation_id)


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
    metadata = invitation.metadata_payload or {}
    workspace_id, invalid_workspace_scope = _workspace_id_from_metadata(metadata)
    rbac = RbacService(session=session)
    if invalid_workspace_scope or not _can_manage_invitation_scope(
        actor=actor,
        rbac=rbac,
        workspace_id=workspace_id,
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
    metadata = invitation.metadata_payload or {}
    workspace_id, invalid_workspace_scope = _workspace_id_from_metadata(metadata)
    rbac = RbacService(session=session)
    if invalid_workspace_scope or not _can_manage_invitation_scope(
        actor=actor,
        rbac=rbac,
        workspace_id=workspace_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return service.cancel_invitation(invitation_id=invitation_id)


__all__ = ["router"]
