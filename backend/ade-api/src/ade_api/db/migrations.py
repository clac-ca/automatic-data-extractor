"""Compatibility wrapper for shared DB migrations."""

from ade_db.migrations_runner import migration_timeout_seconds, run_migrations, run_migrations_async

__all__ = [
    "run_migrations",
    "run_migrations_async",
    "migration_timeout_seconds",
]
