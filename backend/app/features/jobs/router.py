from typing import Iterable

from fastapi import APIRouter

from .schemas import Job
from .service import list_jobs as list_jobs_service

router = APIRouter()


@router.get("/", response_model=list[Job])
async def list_jobs() -> Iterable[Job]:
    return list(list_jobs_service())
