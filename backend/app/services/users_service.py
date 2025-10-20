from typing import Iterable

from ..repositories.users_repo import InMemoryUsersRepository
from ..schemas.users import User

_repo = InMemoryUsersRepository()


def list_users() -> Iterable[User]:
    return _repo.list()
