from typing import Iterable

from ..repositories.jobs_repo import InMemoryJobsRepository
from ..schemas.jobs import Job

_repo = InMemoryJobsRepository()


def list_jobs() -> Iterable[Job]:
    return _repo.list()
