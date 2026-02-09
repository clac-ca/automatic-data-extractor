"""RBAC feature package."""

from ade_api.core.rbac.types import ScopeType

from .service import (
    AssignmentError,
    AssignmentNotFoundError,
    AuthorizationDecision,
    AuthorizationError,
    RbacService,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleValidationError,
    ScopeMismatchError,
    authorize,
    collect_permission_keys,
)

__all__ = [
    "AssignmentError",
    "AssignmentNotFoundError",
    "AuthorizationDecision",
    "AuthorizationError",
    "RbacService",
    "RoleConflictError",
    "RoleImmutableError",
    "RoleNotFoundError",
    "RoleValidationError",
    "ScopeMismatchError",
    "ScopeType",
    "authorize",
    "collect_permission_keys",
]
