from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Response, Security, status

from ade_api.api.deps import ReadSessionDep, WriteSessionDep
from ade_api.core.http import require_authenticated, require_csrf, require_global
from ade_db.models import User

from .schemas import (
    GroupCreate,
    GroupListResponse,
    GroupMembershipRefCreate,
    GroupMembersResponse,
    GroupOut,
    GroupUpdate,
)
from .service import GroupsService

router = APIRouter(tags=["groups"], dependencies=[Security(require_authenticated)])

GroupPath = Annotated[
    UUID,
    Path(description="Group identifier", alias="groupId"),
]
MemberPath = Annotated[
    UUID,
    Path(description="Member identifier", alias="memberId"),
]


@router.get(
    "/groups",
    response_model=GroupListResponse,
    response_model_exclude_none=True,
    summary="List groups",
)
def list_groups(
    _: Annotated[User, Security(require_global("groups.read_all"))],
    session: ReadSessionDep,
    q: str | None = None,
) -> GroupListResponse:
    service = GroupsService(session=session)
    return service.list_groups(q=q)


@router.post(
    "/groups",
    dependencies=[Security(require_csrf)],
    response_model=GroupOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create group",
)
def create_group(
    _: Annotated[User, Security(require_global("groups.manage_all"))],
    session: WriteSessionDep,
    payload: GroupCreate,
) -> GroupOut:
    service = GroupsService(session=session)
    return service.create_group(payload)


@router.get(
    "/groups/{groupId}",
    response_model=GroupOut,
    response_model_exclude_none=True,
    summary="Get group",
)
def get_group(
    _: Annotated[User, Security(require_global("groups.read_all"))],
    group_id: GroupPath,
    session: ReadSessionDep,
) -> GroupOut:
    service = GroupsService(session=session)
    return service.get_group_out(group_id=group_id)


@router.patch(
    "/groups/{groupId}",
    dependencies=[Security(require_csrf)],
    response_model=GroupOut,
    response_model_exclude_none=True,
    summary="Update group",
)
def update_group(
    _: Annotated[User, Security(require_global("groups.manage_all"))],
    group_id: GroupPath,
    payload: GroupUpdate,
    session: WriteSessionDep,
) -> GroupOut:
    service = GroupsService(session=session)
    return service.update_group(group_id=group_id, payload=payload)


@router.delete(
    "/groups/{groupId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group",
)
def delete_group(
    _: Annotated[User, Security(require_global("groups.manage_all"))],
    group_id: GroupPath,
    session: WriteSessionDep,
) -> Response:
    service = GroupsService(session=session)
    service.delete_group(group_id=group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/groups/{groupId}/members",
    response_model=GroupMembersResponse,
    response_model_exclude_none=True,
    summary="List group members",
)
def list_group_members(
    _: Annotated[User, Security(require_global("groups.members.read_all"))],
    group_id: GroupPath,
    session: ReadSessionDep,
) -> GroupMembersResponse:
    service = GroupsService(session=session)
    return service.list_members(group_id=group_id)


@router.post(
    "/groups/{groupId}/members/$ref",
    dependencies=[Security(require_csrf)],
    response_model=GroupMembersResponse,
    response_model_exclude_none=True,
    summary="Add group member by reference",
)
def add_group_member_ref(
    _: Annotated[User, Security(require_global("groups.members.manage_all"))],
    group_id: GroupPath,
    payload: GroupMembershipRefCreate,
    session: WriteSessionDep,
) -> GroupMembersResponse:
    service = GroupsService(session=session)
    return service.add_member_ref(group_id=group_id, payload=payload)


@router.delete(
    "/groups/{groupId}/members/{memberId}/$ref",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove group member by reference",
)
def remove_group_member_ref(
    _: Annotated[User, Security(require_global("groups.members.manage_all"))],
    group_id: GroupPath,
    member_id: MemberPath,
    session: WriteSessionDep,
) -> Response:
    service = GroupsService(session=session)
    service.remove_member_ref(group_id=group_id, member_id=member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
