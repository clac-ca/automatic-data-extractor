"""Auth contracts and helpers shared across the API surface."""

from .errors import AuthenticationError, PermissionDeniedError
from .pipeline import authenticate_request
from .principal import AuthenticatedPrincipal, AuthVia, PrincipalType

__all__ = [
    "AuthenticatedPrincipal",
    "AuthVia",
    "PrincipalType",
    "AuthenticationError",
    "PermissionDeniedError",
    "authenticate_request",
]
