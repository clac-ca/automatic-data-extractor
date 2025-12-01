"""RBAC feature package."""

from .models import ScopeType
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
