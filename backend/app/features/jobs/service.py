from typing import Iterable

from .repository import InMemoryJobsRepository
from .schemas import Job

_repo = InMemoryJobsRepository()


def list_jobs() -> Iterable[Job]:
    return _repo.list()
