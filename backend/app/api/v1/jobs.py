from typing import Iterable

from fastapi import APIRouter

from ...schemas.jobs import Job
from ...services import jobs_service

router = APIRouter()


@router.get("/", response_model=list[Job])
async def list_jobs() -> Iterable[Job]:
    return list(jobs_service.list_jobs())
