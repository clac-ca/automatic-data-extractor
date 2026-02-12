from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ade_api.core.security import hash_password, mint_opaque_token
from ade_db.models import Group, GroupMembership, GroupMembershipMode, GroupSource, User

from .errors import ScimApiError

_ENTERPRISE_USER_SCHEMA = "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"
_USER_CORE_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
_GROUP_CORE_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_FILTER_RE = re.compile(r"^\s*([A-Za-z][\w]*)\s+eq\s+\"([^\"]*)\"\s*$")
_MEMBER_FILTER_RE = re.compile(r"""^members\[value\s+eq\s+["']([^"']+)["']\]$""")


def _slugify(value: str) -> str:
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or "group"


def _canonical_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _ensure_scim_id(raw: str, *, label: str) -> UUID:
    try:
        return UUID(str(raw).strip())
    except ValueError as exc:
        raise ScimApiError(
            status_code=400,
            detail=f"Invalid {label} value: {raw!r}",
            scim_type="invalidValue",
        ) from exc


class ScimProvisioningService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def list_users(
        self,
        *,
        filter_value: str | None,
        start_index: int,
        count: int,
    ) -> dict[str, Any]:
        stmt = select(User).order_by(User.created_at.asc(), User.id.asc())
        if filter_value:
            stmt = stmt.where(self._build_user_filter(filter_value))

        total = self._session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        offset = max(start_index - 1, 0)
        users = list(self._session.execute(stmt.offset(offset).limit(count)).scalars().all())

        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": int(total),
            "startIndex": start_index,
            "itemsPerPage": len(users),
            "Resources": [self._serialize_user(user) for user in users],
        }

    def get_user(self, *, user_id: UUID) -> dict[str, Any]:
        user = self._session.get(User, user_id)
        if user is None:
            raise ScimApiError(status_code=404, detail="User not found")
        return self._serialize_user(user)

    def create_user(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        email = self._resolve_user_name(payload)
        if not email:
            raise ScimApiError(
                status_code=400, detail="userName is required", scim_type="invalidValue"
            )

        existing = self._session.execute(
            select(User).where(User.email_normalized == email).limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            raise ScimApiError(status_code=409, detail="User already exists")

        user = User(
            email=email,
            hashed_password=hash_password(mint_opaque_token(32)),
            display_name=self._build_display_name(payload),
            given_name=self._extract_nested_str(payload, "name", "givenName"),
            surname=self._extract_nested_str(payload, "name", "familyName"),
            job_title=self._extract_str(payload.get("title")),
            department=self._extract_enterprise_str(payload, "department"),
            employee_id=self._extract_enterprise_str(payload, "employeeNumber"),
            mobile_phone=self._extract_phone(payload, phone_type="mobile"),
            business_phones=self._extract_business_phones(payload),
            source="scim",
            external_id=self._extract_str(payload.get("externalId")),
            is_active=self._extract_bool(payload.get("active"), default=True),
            is_verified=True,
            is_service_account=False,
        )
        self._session.add(user)
        try:
            self._session.flush([user])
        except IntegrityError as exc:
            raise ScimApiError(status_code=409, detail="User conflict") from exc
        return self._serialize_user(user)

    def replace_user(self, *, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        user = self._session.get(User, user_id)
        if user is None:
            raise ScimApiError(status_code=404, detail="User not found")

        email = self._resolve_user_name(payload)
        if not email:
            raise ScimApiError(
                status_code=400, detail="userName is required", scim_type="invalidValue"
            )

        user.email = email
        user.display_name = self._build_display_name(payload)
        user.given_name = self._extract_nested_str(payload, "name", "givenName")
        user.surname = self._extract_nested_str(payload, "name", "familyName")
        user.job_title = self._extract_str(payload.get("title"))
        user.department = self._extract_enterprise_str(payload, "department")
        user.employee_id = self._extract_enterprise_str(payload, "employeeNumber")
        user.mobile_phone = self._extract_phone(payload, phone_type="mobile")
        user.business_phones = self._extract_business_phones(payload)
        user.external_id = self._extract_str(payload.get("externalId"))
        user.source = "scim"
        user.is_active = self._extract_bool(payload.get("active"), default=True)
        try:
            self._session.flush([user])
        except IntegrityError as exc:
            raise ScimApiError(status_code=409, detail="User conflict") from exc
        return self._serialize_user(user)

    def patch_user(self, *, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        user = self._session.get(User, user_id)
        if user is None:
            raise ScimApiError(status_code=404, detail="User not found")

        operations = payload.get("Operations")
        if not isinstance(operations, list):
            raise ScimApiError(
                status_code=400, detail="Operations is required", scim_type="invalidSyntax"
            )

        for op in operations:
            if not isinstance(op, dict):
                continue
            action = str(op.get("op") or "").strip().lower()
            path = str(op.get("path") or "").strip()
            value = op.get("value")
            if action not in {"add", "replace", "remove"}:
                raise ScimApiError(
                    status_code=400, detail="Unsupported PATCH op", scim_type="invalidSyntax"
                )

            if action == "remove":
                self._apply_user_path(user=user, path=path, value=None)
                continue

            if path:
                self._apply_user_path(user=user, path=path, value=value)
                continue

            if isinstance(value, dict):
                for key, nested_value in value.items():
                    self._apply_user_path(user=user, path=str(key), value=nested_value)

        try:
            self._session.flush([user])
        except IntegrityError as exc:
            raise ScimApiError(status_code=409, detail="User conflict") from exc
        return self._serialize_user(user)

    def list_groups(
        self,
        *,
        filter_value: str | None,
        start_index: int,
        count: int,
    ) -> dict[str, Any]:
        stmt = select(Group).order_by(Group.created_at.asc(), Group.id.asc())
        if filter_value:
            stmt = stmt.where(self._build_group_filter(filter_value))
        total = self._session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        offset = max(start_index - 1, 0)
        groups = list(self._session.execute(stmt.offset(offset).limit(count)).scalars().all())

        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": int(total),
            "startIndex": start_index,
            "itemsPerPage": len(groups),
            "Resources": [self._serialize_group(group) for group in groups],
        }

    def get_group(self, *, group_id: UUID) -> dict[str, Any]:
        group = self._session.get(Group, group_id)
        if group is None:
            raise ScimApiError(status_code=404, detail="Group not found")
        return self._serialize_group(group)

    def create_group(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        display_name = self._extract_str(payload.get("displayName"))
        if not display_name:
            raise ScimApiError(
                status_code=400, detail="displayName is required", scim_type="invalidValue"
            )

        group = Group(
            display_name=display_name,
            slug=self._allocate_group_slug(display_name),
            description=self._extract_str(payload.get("description")),
            membership_mode=GroupMembershipMode.DYNAMIC,
            source=GroupSource.IDP,
            external_id=self._extract_str(payload.get("externalId")),
            is_active=True,
        )
        self._session.add(group)
        try:
            self._session.flush([group])
        except IntegrityError as exc:
            raise ScimApiError(status_code=409, detail="Group conflict") from exc

        members = payload.get("members")
        if isinstance(members, list):
            self._replace_group_members(group=group, members=members)
        self._session.flush()
        return self._serialize_group(group)

    def replace_group(self, *, group_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        group = self._session.get(Group, group_id)
        if group is None:
            raise ScimApiError(status_code=404, detail="Group not found")

        display_name = self._extract_str(payload.get("displayName"))
        if not display_name:
            raise ScimApiError(
                status_code=400, detail="displayName is required", scim_type="invalidValue"
            )

        group.display_name = display_name
        group.description = self._extract_str(payload.get("description"))
        group.source = GroupSource.IDP
        group.membership_mode = GroupMembershipMode.DYNAMIC
        group.external_id = self._extract_str(payload.get("externalId"))
        if not group.slug:
            group.slug = self._allocate_group_slug(display_name)
        try:
            self._session.flush([group])

            members = payload.get("members")
            if isinstance(members, list):
                self._replace_group_members(group=group, members=members)
            self._session.flush()
        except IntegrityError as exc:
            raise ScimApiError(status_code=409, detail="Group conflict") from exc
        return self._serialize_group(group)

    def patch_group(self, *, group_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        group = self._session.get(Group, group_id)
        if group is None:
            raise ScimApiError(status_code=404, detail="Group not found")

        operations = payload.get("Operations")
        if not isinstance(operations, list):
            raise ScimApiError(
                status_code=400, detail="Operations is required", scim_type="invalidSyntax"
            )

        for op in operations:
            if not isinstance(op, dict):
                continue
            action = str(op.get("op") or "").strip().lower()
            path = str(op.get("path") or "").strip()
            value = op.get("value")
            if action not in {"add", "replace", "remove"}:
                raise ScimApiError(
                    status_code=400, detail="Unsupported PATCH op", scim_type="invalidSyntax"
                )

            if path in {"displayName", "description", "externalId"}:
                if action == "remove":
                    self._apply_group_scalar_path(group=group, path=path, value=None)
                else:
                    self._apply_group_scalar_path(group=group, path=path, value=value)
                continue

            if path == "members" or path.startswith("members["):
                self._apply_group_member_patch(
                    group=group,
                    action=action,
                    path=path,
                    value=value,
                )
                continue
            if path.startswith("members"):
                raise ScimApiError(
                    status_code=400,
                    detail=f"Unsupported members path: {path}",
                    scim_type="invalidPath",
                )
                continue

            if not path and isinstance(value, dict):
                for key, nested_value in value.items():
                    if key == "members":
                        self._apply_group_member_patch(
                            group=group, action=action, value=nested_value
                        )
                    else:
                        self._apply_group_scalar_path(group=group, path=key, value=nested_value)

        group.source = GroupSource.IDP
        group.membership_mode = GroupMembershipMode.DYNAMIC
        try:
            self._session.flush([group])
            self._session.flush()
        except IntegrityError as exc:
            raise ScimApiError(status_code=409, detail="Group conflict") from exc
        return self._serialize_group(group)

    def _apply_group_member_patch(
        self,
        *,
        group: Group,
        action: str,
        path: str = "members",
        value: Any,
    ) -> None:
        if path != "members":
            if action != "remove" or value is not None:
                raise ScimApiError(
                    status_code=400,
                    detail=f"Unsupported members path: {path}",
                    scim_type="invalidPath",
                )
            user_id = self._parse_member_filter_user_id(path)
            membership = self._session.execute(
                select(GroupMembership).where(
                    GroupMembership.group_id == group.id,
                    GroupMembership.user_id == user_id,
                )
            ).scalar_one_or_none()
            if membership is not None:
                self._session.delete(membership)
            return

        if action == "remove" and value is None:
            for membership in self._session.execute(
                select(GroupMembership).where(GroupMembership.group_id == group.id)
            ).scalars():
                self._session.delete(membership)
            return

        if isinstance(value, dict):
            members = [value]
        elif isinstance(value, list):
            members = [item for item in value if isinstance(item, dict)]
        else:
            raise ScimApiError(
                status_code=400, detail="Invalid members payload", scim_type="invalidValue"
            )

        member_ids = {
            _ensure_scim_id(str(member["value"]), label="member value")
            for member in members
            if member.get("value") is not None
        }
        if not member_ids:
            return

        existing_users = {
            user.id
            for user in self._session.execute(
                select(User).where(User.id.in_(tuple(member_ids)))
            ).scalars()
        }
        missing = member_ids - existing_users
        if missing:
            raise ScimApiError(
                status_code=400,
                detail=f"Unknown member ids: {', '.join(sorted(str(item) for item in missing))}",
                scim_type="invalidValue",
            )

        existing_memberships = {
            membership.user_id: membership
            for membership in self._session.execute(
                select(GroupMembership).where(GroupMembership.group_id == group.id)
            ).scalars()
        }

        if action in {"add", "replace"}:
            for user_id in member_ids:
                if user_id in existing_memberships:
                    continue
                self._session.add(
                    GroupMembership(
                        group_id=group.id,
                        user_id=user_id,
                        membership_source="idp",
                    )
                )

        if action in {"remove", "replace"}:
            remove_ids = (
                member_ids if action == "remove" else set(existing_memberships) - member_ids
            )
            for user_id in remove_ids:
                membership = existing_memberships.get(user_id)
                if membership is not None:
                    self._session.delete(membership)

    def _replace_group_members(self, *, group: Group, members: list[Any]) -> None:
        parsed_members = [member for member in members if isinstance(member, dict)]
        self._apply_group_member_patch(group=group, action="replace", value=parsed_members)

    @staticmethod
    def _parse_member_filter_user_id(path: str) -> UUID:
        match = _MEMBER_FILTER_RE.match(path)
        if match is None:
            raise ScimApiError(
                status_code=400,
                detail=f"Unsupported members path: {path}",
                scim_type="invalidPath",
            )
        return _ensure_scim_id(match.group(1), label="member value")

    @staticmethod
    def _apply_group_scalar_path(*, group: Group, path: str, value: Any) -> None:
        if path == "displayName":
            group.display_name = str(value).strip() if value is not None else group.display_name
        elif path == "description":
            group.description = str(value).strip() if value is not None else None
        elif path == "externalId":
            group.external_id = str(value).strip() if value is not None else None

    @staticmethod
    def _extract_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _extract_bool(value: Any, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        return default

    @staticmethod
    def _extract_nested_str(payload: dict[str, Any], key: str, nested_key: str) -> str | None:
        raw = payload.get(key)
        if not isinstance(raw, dict):
            return None
        value = raw.get(nested_key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _extract_enterprise_str(self, payload: dict[str, Any], field: str) -> str | None:
        extension = payload.get(_ENTERPRISE_USER_SCHEMA)
        if not isinstance(extension, dict):
            return None
        return self._extract_str(extension.get(field))

    def _extract_phone(self, payload: dict[str, Any], *, phone_type: str) -> str | None:
        phone_numbers = payload.get("phoneNumbers")
        if not isinstance(phone_numbers, list):
            return None
        for item in phone_numbers:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() != phone_type:
                continue
            value = self._extract_str(item.get("value"))
            if value:
                return value
        return None

    def _extract_business_phones(self, payload: dict[str, Any]) -> str | None:
        phone_numbers = payload.get("phoneNumbers")
        if not isinstance(phone_numbers, list):
            return None
        business_values: list[str] = []
        for item in phone_numbers:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip().lower()
            if item_type not in {"work", "business"}:
                continue
            value = self._extract_str(item.get("value"))
            if value:
                business_values.append(value)
        if not business_values:
            return None
        return json.dumps(business_values)

    def _resolve_user_name(self, payload: dict[str, Any]) -> str | None:
        direct = _canonical_email(self._extract_str(payload.get("userName")))
        if direct:
            return direct
        emails = payload.get("emails")
        if not isinstance(emails, list):
            return None
        for item in emails:
            if not isinstance(item, dict):
                continue
            value = _canonical_email(self._extract_str(item.get("value")))
            if value:
                return value
        return None

    def _build_display_name(self, payload: dict[str, Any]) -> str | None:
        display_name = self._extract_str(payload.get("displayName"))
        if display_name:
            return display_name
        given = self._extract_nested_str(payload, "name", "givenName")
        family = self._extract_nested_str(payload, "name", "familyName")
        combined = " ".join(part for part in [given, family] if part)
        return combined or None

    def _serialize_user(self, user: User) -> dict[str, Any]:
        emails: list[dict[str, Any]] = []
        if user.email_normalized:
            emails.append({"value": user.email_normalized, "primary": True})

        phone_numbers: list[dict[str, Any]] = []
        if user.mobile_phone:
            phone_numbers.append({"value": user.mobile_phone, "type": "mobile"})
        if user.business_phones:
            try:
                phones = json.loads(user.business_phones)
                if isinstance(phones, list):
                    phone_numbers.extend(
                        {"value": str(item), "type": "work"} for item in phones if str(item).strip()
                    )
            except ValueError:
                phone_numbers.append({"value": user.business_phones, "type": "work"})

        payload: dict[str, Any] = {
            "schemas": [_USER_CORE_SCHEMA, _ENTERPRISE_USER_SCHEMA],
            "id": str(user.id),
            "externalId": user.external_id,
            "userName": user.email_normalized,
            "active": bool(user.is_active),
            "displayName": user.display_name,
            "emails": emails,
            "name": {
                "givenName": user.given_name,
                "familyName": user.surname,
            },
            "title": user.job_title,
            "phoneNumbers": phone_numbers,
            _ENTERPRISE_USER_SCHEMA: {
                "department": user.department,
                "employeeNumber": user.employee_id,
            },
        }
        return _remove_none(payload)

    def _serialize_group(self, group: Group) -> dict[str, Any]:
        members = [
            {"value": str(membership.user_id)}
            for membership in self._session.execute(
                select(GroupMembership).where(GroupMembership.group_id == group.id)
            ).scalars()
        ]
        payload: dict[str, Any] = {
            "schemas": [_GROUP_CORE_SCHEMA],
            "id": str(group.id),
            "externalId": group.external_id,
            "displayName": group.display_name,
            "description": group.description,
            "members": members,
        }
        return _remove_none(payload)

    def _build_user_filter(self, filter_value: str) -> ColumnElement[bool]:
        field, value = self._parse_eq_filter(filter_value)
        if field == "id":
            return User.id == _ensure_scim_id(value, label="id")
        if field == "userName":
            return User.email_normalized == value.strip().lower()
        if field == "externalId":
            return User.external_id == value
        raise ScimApiError(
            status_code=400, detail=f"Unsupported filter field: {field}", scim_type="invalidFilter"
        )

    def _build_group_filter(self, filter_value: str) -> ColumnElement[bool]:
        field, value = self._parse_eq_filter(filter_value)
        if field == "id":
            return Group.id == _ensure_scim_id(value, label="id")
        if field == "displayName":
            return Group.display_name == value
        if field == "externalId":
            return Group.external_id == value
        raise ScimApiError(
            status_code=400, detail=f"Unsupported filter field: {field}", scim_type="invalidFilter"
        )

    @staticmethod
    def _parse_eq_filter(filter_value: str) -> tuple[str, str]:
        match = _FILTER_RE.match(filter_value)
        if match is None:
            raise ScimApiError(
                status_code=400, detail="Unsupported filter syntax", scim_type="invalidFilter"
            )
        field, value = match.group(1), match.group(2)
        return field, value

    def _apply_user_path(self, *, user: User, path: str, value: Any) -> None:
        if path == "active":
            user.is_active = self._extract_bool(value, default=user.is_active)
            return
        if path == "displayName":
            user.display_name = self._extract_str(value)
            return
        if path == "userName":
            email = _canonical_email(self._extract_str(value))
            if email:
                user.email = email
            return
        if path == "externalId":
            user.external_id = self._extract_str(value)
            user.source = "scim"
            return
        if path == "title":
            user.job_title = self._extract_str(value)
            return
        if path == "name.givenName":
            user.given_name = self._extract_str(value)
            return
        if path == "name.familyName":
            user.surname = self._extract_str(value)
            return
        if path == "emails" and isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                email = _canonical_email(self._extract_str(item.get("value")))
                if email:
                    user.email = email
                    break
            return
        if path in {"phoneNumbers", 'phoneNumbers[type eq "mobile"].value'}:
            if isinstance(value, list):
                user.mobile_phone = self._extract_phone(
                    {"phoneNumbers": value}, phone_type="mobile"
                )
                user.business_phones = self._extract_business_phones({"phoneNumbers": value})
            elif isinstance(value, str):
                user.mobile_phone = value.strip() or None
            return

    def _allocate_group_slug(self, display_name: str) -> str:
        base = _slugify(display_name)
        slug = base
        while self._session.execute(
            select(Group.id).where(Group.slug == slug).limit(1)
        ).scalar_one_or_none():
            slug = f"{base}-{uuid4().hex[:6]}"
        return slug


def _remove_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _remove_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_remove_none(v) for v in value if v is not None]
    return value


__all__ = ["ScimProvisioningService"]
