"""Shared auth/permission error types."""


class AuthenticationError(Exception):
    """Raised when a request cannot be authenticated."""


class PermissionDeniedError(Exception):
    """Raised when a principal lacks a required permission."""

    def __init__(
        self,
        permission_key: str,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> None:
        self.permission_key = permission_key
        self.scope_type = scope_type
        self.scope_id = scope_id
        msg = f"Permission '{permission_key}' denied"
        if scope_type:
            msg = f"{msg} for scope '{scope_type}'"
        super().__init__(msg)

