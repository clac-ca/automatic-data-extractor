from typing import Iterable

from .repository import InMemoryUsersRepository
from .schemas import User

_repo = InMemoryUsersRepository()


def list_users() -> Iterable[User]:
    return _repo.list()
