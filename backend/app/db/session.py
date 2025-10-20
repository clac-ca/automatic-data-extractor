"""
Database session placeholder.
Replace with actual engine/session wiring when persistence is introduced.
"""

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def get_session() -> Iterator[None]:
    """
    Yield a database session/connection.
    Currently a stub to keep the application structure ready for a DB layer.
    """
    # When integrating SQLAlchemy or another ORM, initialize the engine here.
    yield
