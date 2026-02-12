from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.time import utc_now
from ade_api.core.security.hashing import hash_password
from ade_api.core.security.tokens import mint_opaque_token
from ade_api.features.rbac.service import (
    AssignmentError,
    RbacService,
    RoleNotFoundError,
    ScopeMismatchError,
)
from ade_db.models import (
    AssignmentScopeType,
    Invitation,
    InvitationStatus,
    PrincipalType,
    User,
)

from .schemas import InvitationCreate, InvitationListResponse, InvitationOut


class InvitationsService:
    def __init__(self, *, session: Session) -> None:
        self._session = session
        self._rbac = RbacService(session=session)

    @staticmethod
    def _serialize(invitation: Invitation) -> InvitationOut:
        return InvitationOut(
            id=invitation.id,
            email_normalized=invitation.email_normalized,
            invited_user_id=invitation.invited_user_id,
            invited_by_user_id=invitation.invited_by_user_id,
            status=invitation.status,
            expires_at=invitation.expires_at,
            redeemed_at=invitation.redeemed_at,
            metadata=invitation.metadata_payload,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
        )

    def list_invitations(
        self,
        *,
        workspace_id: UUID | None = None,
        status_value: InvitationStatus | None = None,
    ) -> InvitationListResponse:
        stmt = select(Invitation).order_by(Invitation.created_at.desc(), Invitation.id.desc())
        invitations = list(self._session.execute(stmt).scalars().all())
        filtered: list[Invitation] = []
        for invitation in invitations:
            metadata = invitation.metadata_payload or {}
            metadata_workspace = metadata.get("workspaceId")
            if workspace_id is not None and str(metadata_workspace or "") != str(workspace_id):
                continue
            if status_value is not None and invitation.status != status_value:
                continue
            filtered.append(invitation)
        return InvitationListResponse(items=[self._serialize(item) for item in filtered])

    def get_invitation(self, *, invitation_id: UUID) -> Invitation:
        invitation = self._session.get(Invitation, invitation_id)
        if invitation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
        return invitation

    def get_invitation_out(self, *, invitation_id: UUID) -> InvitationOut:
        return self._serialize(self.get_invitation(invitation_id=invitation_id))

    def create_invitation(self, *, payload: InvitationCreate, actor: User) -> InvitationOut:
        canonical_email = str(payload.invited_user_email).strip().lower()
        existing_user = self._session.execute(
            select(User).where(User.email_normalized == canonical_email).limit(1)
        ).scalar_one_or_none()

        invited_user = existing_user
        if invited_user is None:
            invited_user = User(
                email=canonical_email,
                hashed_password=hash_password(mint_opaque_token(32)),
                display_name=payload.display_name,
                is_active=True,
                is_verified=False,
                is_service_account=False,
                source="internal",
            )
            self._session.add(invited_user)
            try:
                self._session.flush([invited_user])
            except IntegrityError as exc:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Email already in use",
                ) from exc

        metadata_payload: dict[str, object] = {}
        if payload.workspace_context is not None:
            metadata_payload["workspaceId"] = str(payload.workspace_context.workspace_id)
            metadata_payload["roleAssignments"] = [
                {"roleId": str(item.role_id)} for item in payload.workspace_context.role_assignments
            ]

        invitation = Invitation(
            email_normalized=canonical_email,
            invited_user_id=invited_user.id,
            invited_by_user_id=actor.id,
            status=InvitationStatus.PENDING,
            expires_at=utc_now() + timedelta(days=7),
            redeemed_at=None,
            metadata_payload=metadata_payload or None,
        )
        self._session.add(invitation)
        self._session.flush([invitation])

        if payload.workspace_context is not None:
            for assignment in payload.workspace_context.role_assignments:
                try:
                    self._rbac.assign_principal_role_if_missing(
                        principal_type=PrincipalType.USER,
                        principal_id=invited_user.id,
                        role_id=assignment.role_id,
                        scope_type=AssignmentScopeType.WORKSPACE,
                        scope_id=payload.workspace_context.workspace_id,
                    )
                except (RoleNotFoundError, AssignmentError) as exc:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
                except ScopeMismatchError as exc:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=str(exc),
                    ) from exc

        return self._serialize(invitation)

    def resend_invitation(self, *, invitation_id: UUID) -> InvitationOut:
        invitation = self.get_invitation(invitation_id=invitation_id)
        if invitation.status != InvitationStatus.CANCELLED:
            invitation.status = InvitationStatus.PENDING
        invitation.expires_at = utc_now() + timedelta(days=7)
        self._session.flush([invitation])
        return self._serialize(invitation)

    def cancel_invitation(self, *, invitation_id: UUID) -> InvitationOut:
        invitation = self.get_invitation(invitation_id=invitation_id)
        invitation.status = InvitationStatus.CANCELLED
        self._session.flush([invitation])
        return self._serialize(invitation)


__all__ = ["InvitationsService"]
