from typing import Iterable, Optional

from app.shared.repositories.base import Repository

from .schemas import Job


class InMemoryJobsRepository(Repository[Job]):
    def __init__(self) -> None:
        self._jobs = {}

    def list(self) -> Iterable[Job]:
        return self._jobs.values()

    def get(self, item_id: str) -> Optional[Job]:
        return self._jobs.get(item_id)
