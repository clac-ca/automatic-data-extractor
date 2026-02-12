from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import String, and_, cast, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ade_api.common.cursor_listing import (
    ResolvedCursorSort,
    paginate_query_cursor,
)
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

from .schemas import (
    InvitationCreate,
    InvitationLifecycleStatus,
    InvitationOut,
    InvitationPage,
    InvitationRoleAssignmentOut,
    InvitationWorkspaceContextOut,
)


class InvitationsService:
    def __init__(self, *, session: Session) -> None:
        self._session = session
        self._rbac = RbacService(session=session)

    @classmethod
    def _serialize(cls, invitation: Invitation, *, now: datetime | None = None) -> InvitationOut:
        return InvitationOut(
            id=invitation.id,
            email_normalized=invitation.email_normalized,
            invited_user_id=invitation.invited_user_id,
            invited_by_user_id=invitation.invited_by_user_id,
            workspace_id=invitation.workspace_id,
            status=cls._effective_status(invitation=invitation, now=now),
            expires_at=invitation.expires_at,
            redeemed_at=invitation.redeemed_at,
            workspace_context=cls._serialize_workspace_context(invitation),
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
        )

    def serialize_invitation(
        self,
        invitation: Invitation,
        *,
        now: datetime | None = None,
    ) -> InvitationOut:
        return self._serialize(invitation, now=now)

    def list_invitations(
        self,
        *,
        workspace_id: UUID | None = None,
        status_value: InvitationLifecycleStatus | None = None,
        q: str | None = None,
        resolved_sort: ResolvedCursorSort[Invitation],
        limit: int,
        cursor: str | None,
        include_total: bool,
    ) -> InvitationPage:
        stmt = select(Invitation)
        now = utc_now()
        predicates: list[ColumnElement[bool]] = []

        if workspace_id is not None:
            predicates.append(Invitation.workspace_id == workspace_id)

        status_predicate = self._status_predicate(status_value=status_value, now=now)
        if status_predicate is not None:
            predicates.append(status_predicate)

        if q:
            token_predicates: list[ColumnElement[bool]] = []
            for token in q.split():
                pattern = f"%{token}%"
                token_predicates.append(
                    or_(
                        Invitation.email_normalized.ilike(pattern),
                        cast(Invitation.invited_by_user_id, String).ilike(pattern),
                    )
                )
            if token_predicates:
                predicates.append(and_(*token_predicates))

        if predicates:
            stmt = stmt.where(and_(*predicates))

        page = paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
        )
        return InvitationPage(
            items=[self._serialize(item, now=now) for item in page.items],
            meta=page.meta,
            facets=page.facets,
        )

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
        workspace_scope_id: UUID | None = None
        if payload.workspace_context is not None:
            workspace_scope_id = payload.workspace_context.workspace_id
            metadata_payload["roleAssignments"] = [
                {"roleId": str(item.role_id)} for item in payload.workspace_context.role_assignments
            ]

        invitation = Invitation(
            email_normalized=canonical_email,
            invited_user_id=invited_user.id,
            invited_by_user_id=actor.id,
            workspace_id=workspace_scope_id,
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
        if invitation.status in {InvitationStatus.CANCELLED, InvitationStatus.ACCEPTED}:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Only pending invitations can be resent",
            )
        invitation.status = InvitationStatus.PENDING
        invitation.expires_at = utc_now() + timedelta(days=7)
        self._session.flush([invitation])
        return self._serialize(invitation)

    def cancel_invitation(self, *, invitation_id: UUID) -> InvitationOut:
        invitation = self.get_invitation(invitation_id=invitation_id)
        if invitation.status in {InvitationStatus.CANCELLED, InvitationStatus.ACCEPTED}:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Only pending invitations can be cancelled",
            )
        invitation.status = InvitationStatus.CANCELLED
        self._session.flush([invitation])
        return self._serialize(invitation)

    @staticmethod
    def _extract_role_assignments(
        metadata_payload: dict[str, object] | None,
    ) -> list[InvitationRoleAssignmentOut]:
        if metadata_payload is None:
            return []
        role_assignments = metadata_payload.get("roleAssignments")
        if not isinstance(role_assignments, list):
            return []

        parsed: list[InvitationRoleAssignmentOut] = []
        for assignment in role_assignments:
            if not isinstance(assignment, dict):
                continue
            role_raw = assignment.get("roleId")
            if role_raw is None:
                continue
            try:
                parsed.append(InvitationRoleAssignmentOut(role_id=UUID(str(role_raw))))
            except (TypeError, ValueError):
                continue
        return parsed

    @classmethod
    def _serialize_workspace_context(
        cls,
        invitation: Invitation,
    ) -> InvitationWorkspaceContextOut | None:
        if invitation.workspace_id is None:
            return None
        return InvitationWorkspaceContextOut(
            workspace_id=invitation.workspace_id,
            role_assignments=cls._extract_role_assignments(invitation.metadata_payload),
        )

    @staticmethod
    def _is_effectively_expired(
        *,
        invitation: Invitation,
        now: datetime | None = None,
    ) -> bool:
        if invitation.status != InvitationStatus.PENDING:
            return False
        if invitation.expires_at is None:
            return False
        timestamp = now or utc_now()
        return invitation.expires_at <= timestamp

    @classmethod
    def _effective_status(
        cls,
        *,
        invitation: Invitation,
        now: datetime | None = None,
    ) -> InvitationLifecycleStatus:
        if cls._is_effectively_expired(invitation=invitation, now=now):
            return InvitationLifecycleStatus.EXPIRED
        if invitation.status == InvitationStatus.PENDING:
            return InvitationLifecycleStatus.PENDING
        if invitation.status == InvitationStatus.ACCEPTED:
            return InvitationLifecycleStatus.ACCEPTED
        return InvitationLifecycleStatus.CANCELLED

    @staticmethod
    def _status_predicate(
        *,
        status_value: InvitationLifecycleStatus | None,
        now: datetime,
    ) -> ColumnElement[bool] | None:
        if status_value is None:
            return None
        if status_value == InvitationLifecycleStatus.PENDING:
            return and_(
                Invitation.status == InvitationStatus.PENDING,
                or_(Invitation.expires_at.is_(None), Invitation.expires_at > now),
            )
        if status_value == InvitationLifecycleStatus.EXPIRED:
            return and_(
                Invitation.status == InvitationStatus.PENDING,
                Invitation.expires_at.is_not(None),
                Invitation.expires_at <= now,
            )
        if status_value == InvitationLifecycleStatus.ACCEPTED:
            return Invitation.status == InvitationStatus.ACCEPTED
        return Invitation.status == InvitationStatus.CANCELLED


__all__ = ["InvitationsService"]
