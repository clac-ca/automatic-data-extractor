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
from .session_cookie import clear_session_cookie, set_session_cookie

__all__ = [
    "get_current_principal",
    "get_rbac_service",
    "require_authenticated",
    "require_csrf",
    "require_permission",
    "require_global",
    "require_workspace",
    "register_auth_exception_handlers",
    "set_session_cookie",
    "clear_session_cookie",
]
