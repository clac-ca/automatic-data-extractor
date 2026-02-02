"""HTTP dependency helpers built on the shared auth/RBAC contracts."""

from .dependencies import (
    get_current_principal,
    get_rbac_service,
    require_authenticated,
    require_csrf,
    require_global,
    require_permission,
    require_workspace,
)
from .errors import register_auth_exception_handlers

__all__ = [
    "get_current_principal",
    "get_rbac_service",
    "require_authenticated",
    "require_csrf",
    "require_permission",
    "require_global",
    "require_workspace",
    "register_auth_exception_handlers",
]
