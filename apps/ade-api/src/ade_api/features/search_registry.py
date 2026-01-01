"""Search registry mapping resource names to searchable fields."""

from __future__ import annotations

from sqlalchemy import String, case, cast

from ade_api.common.search import SearchField, SearchRegistry, build_like_predicate
from ade_api.models import (
    ApiKey,
    Build,
    Configuration,
    Document,
    DocumentStatus,
    DocumentTag,
    Permission,
    Role,
    Run,
    User,
    UserRoleAssignment,
    Workspace,
)


def _field(field_id: str, column) -> SearchField:
    return SearchField(field_id, build_like_predicate(column))


def _field_cast(field_id: str, column) -> SearchField:
    return SearchField(field_id, build_like_predicate(cast(column, String)))


def _has_field(field_id: str, relationship, column) -> SearchField:
    predicate = build_like_predicate(column)

    def _builder(token: str):
        return relationship.has(predicate(token))

    return SearchField(field_id, _builder)


def _any_field(field_id: str, relationship, column) -> SearchField:
    predicate = build_like_predicate(column)

    def _builder(token: str):
        return relationship.any(predicate(token))

    return SearchField(field_id, _builder)


_DOCUMENT_STATUS_DISPLAY = case(
    (Document.status == DocumentStatus.ARCHIVED, "archived"),
    (Document.status == DocumentStatus.FAILED, "failed"),
    (Document.status == DocumentStatus.PROCESSED, "ready"),
    (Document.status == DocumentStatus.PROCESSING, "processing"),
    else_="queued",
)

_ASSIGNMENT_SCOPE_TYPE = case(
    (UserRoleAssignment.workspace_id.is_(None), "global"),
    else_="workspace",
)


SEARCH_REGISTRY = SearchRegistry(
    {
        "documents": [
            _field("name", Document.original_filename),
            _field("status", _DOCUMENT_STATUS_DISPLAY),
            _has_field("uploaderName", Document.uploaded_by_user, User.display_name),
            _has_field("uploaderEmail", Document.uploaded_by_user, User.email),
            _any_field("tags", Document.tags, DocumentTag.tag),
        ],
        "runs": [
            _field_cast("id", Run.id),
            _field_cast("status", Run.status),
            _field_cast("configurationId", Run.configuration_id),
            _field("inputFilename", Document.original_filename),
        ],
        "configurations": [
            _field("displayName", Configuration.display_name),
            _field_cast("status", Configuration.status),
        ],
        "builds": [
            _field_cast("id", Build.id),
            _field_cast("status", Build.status),
            _field("summary", Build.summary),
            _field("errorMessage", Build.error_message),
        ],
        "users": [
            _field("email", User.email),
            _field("displayName", User.display_name),
        ],
        "apikeys": [
            _field("name", ApiKey.name),
            _field("prefix", ApiKey.prefix),
        ],
        "workspaces": [
            _field("name", Workspace.name),
            _field("slug", Workspace.slug),
        ],
        "members": [
            _field_cast("userId", UserRoleAssignment.user_id),
            _has_field("roleSlugs", UserRoleAssignment.role, Role.slug),
        ],
        "permissions": [
            _field("key", Permission.key),
            _field("resource", Permission.resource),
            _field("action", Permission.action),
            _field("label", Permission.label),
        ],
        "roles": [
            _field("name", Role.name),
            _field("slug", Role.slug),
            _field("description", Role.description),
        ],
        "roleassignments": [
            _field_cast("userId", UserRoleAssignment.user_id),
            _has_field("roleSlug", UserRoleAssignment.role, Role.slug),
            _field("scopeType", _ASSIGNMENT_SCOPE_TYPE),
            _field_cast("scopeId", UserRoleAssignment.workspace_id),
        ],
    }
)

__all__ = ["SEARCH_REGISTRY"]
