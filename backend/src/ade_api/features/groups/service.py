from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_db.models import Group, GroupMembership, GroupMembershipMode, GroupSource, User

from .schemas import (
    GroupCreate,
    GroupListResponse,
    GroupMemberOut,
    GroupMembershipRefCreate,
    GroupMembersResponse,
    GroupOut,
    GroupUpdate,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or "group"


class GroupsService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    @staticmethod
    def _serialize_group(group: Group) -> GroupOut:
        return GroupOut(
            id=group.id,
            display_name=group.display_name,
            slug=group.slug,
            description=group.description,
            membership_mode=group.membership_mode,
            source=group.source,
            external_id=group.external_id,
            is_active=group.is_active,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    def list_groups(self, *, q: str | None = None) -> GroupListResponse:
        stmt = select(Group).order_by(Group.display_name.asc(), Group.id.asc())
        groups = list(self._session.execute(stmt).scalars().all())
        if q:
            token = q.strip().lower()
            groups = [
                group
                for group in groups
                if token in group.display_name.lower()
                or token in group.slug.lower()
                or token in (group.description or "").lower()
            ]
        return GroupListResponse(items=[self._serialize_group(group) for group in groups])

    def create_group(self, payload: GroupCreate) -> GroupOut:
        slug = _slugify(payload.slug or payload.display_name)
        group = Group(
            display_name=payload.display_name.strip(),
            slug=slug,
            description=payload.description,
            membership_mode=payload.membership_mode,
            source=payload.source,
            external_id=payload.external_id,
            is_active=True,
        )
        self._session.add(group)
        try:
            self._session.flush([group])
        except IntegrityError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Group slug or external mapping already exists",
            ) from exc
        return self._serialize_group(group)

    def get_group(self, *, group_id: UUID) -> Group:
        group = self._session.get(Group, group_id)
        if group is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Group not found")
        return group

    def get_group_out(self, *, group_id: UUID) -> GroupOut:
        return self._serialize_group(self.get_group(group_id=group_id))

    def update_group(self, *, group_id: UUID, payload: GroupUpdate) -> GroupOut:
        group = self.get_group(group_id=group_id)
        updates = payload.model_dump(exclude_unset=True)
        if "display_name" in updates and updates["display_name"] is not None:
            group.display_name = updates["display_name"].strip()
        if "description" in updates:
            group.description = updates["description"]
        if "membership_mode" in updates and updates["membership_mode"] is not None:
            group.membership_mode = updates["membership_mode"]
        if "is_active" in updates and updates["is_active"] is not None:
            group.is_active = bool(updates["is_active"])
        if "external_id" in updates:
            group.external_id = updates["external_id"]
        try:
            self._session.flush([group])
        except IntegrityError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Group external mapping already exists",
            ) from exc
        return self._serialize_group(group)

    def delete_group(self, *, group_id: UUID) -> None:
        group = self.get_group(group_id=group_id)
        self._session.delete(group)
        self._session.flush()

    def list_members(self, *, group_id: UUID) -> GroupMembersResponse:
        self.get_group(group_id=group_id)
        stmt = (
            select(User)
            .join(GroupMembership, GroupMembership.user_id == User.id)
            .where(GroupMembership.group_id == group_id)
            .order_by(User.display_name.asc().nulls_last(), User.email.asc())
        )
        users = list(self._session.execute(stmt).scalars().all())
        return GroupMembersResponse(
            items=[
                GroupMemberOut(
                    user_id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                )
                for user in users
            ]
        )

    def add_member_ref(
        self,
        *,
        group_id: UUID,
        payload: GroupMembershipRefCreate,
    ) -> GroupMembersResponse:
        group = self.get_group(group_id=group_id)
        if group.membership_mode == GroupMembershipMode.DYNAMIC or group.source == GroupSource.IDP:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Provider-managed group memberships are read-only",
            )
        user = self._session.get(User, payload.member_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

        existing_stmt = select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == payload.member_id,
        )
        if self._session.execute(existing_stmt).scalar_one_or_none() is None:
            self._session.add(
                GroupMembership(
                    group_id=group_id,
                    user_id=payload.member_id,
                    membership_source="internal",
                )
            )
            self._session.flush()
        return self.list_members(group_id=group_id)

    def remove_member_ref(self, *, group_id: UUID, member_id: UUID) -> None:
        group = self.get_group(group_id=group_id)
        if group.membership_mode == GroupMembershipMode.DYNAMIC or group.source == GroupSource.IDP:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Provider-managed group memberships are read-only",
            )
        stmt = select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == member_id,
        )
        membership = self._session.execute(stmt).scalar_one_or_none()
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Group membership not found")
        self._session.delete(membership)
        self._session.flush()


__all__ = ["GroupsService"]
