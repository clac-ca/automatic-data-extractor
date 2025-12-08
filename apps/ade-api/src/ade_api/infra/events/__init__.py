"""Event streaming and persistence helpers.

Features are free to implement their own event semantics, but should reuse the
shared NDJSON + dispatcher primitives here to stay consistent.
"""

__all__ = [
    "base",
    "ndjson",
    "scoped_dispatcher",
    "utils",
]
