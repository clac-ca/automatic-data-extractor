from typing import Iterable, Optional

from app.shared.repositories.base import Repository

from .schemas import User


class InMemoryUsersRepository(Repository[User]):
    def __init__(self) -> None:
        self._users = {
            "demo": User(id="demo", email="demo@example.com", full_name="Demo User"),
        }

    def list(self) -> Iterable[User]:
        return self._users.values()

    def get(self, item_id: str) -> Optional[User]:
        return self._users.get(item_id)
