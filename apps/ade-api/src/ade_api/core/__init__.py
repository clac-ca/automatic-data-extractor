"""Shared Identity & Access foundation layer.

This package holds the stable contracts and utilities that feature modules
depend on (auth, API keys, RBAC, me, etc.). Keep dependencies pointed
inwards here to avoid cross-feature coupling.
"""

__all__ = [
    "auth",
    "http",
    "rbac",
    "security",
]
