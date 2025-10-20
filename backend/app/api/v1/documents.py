from typing import Iterable

from fastapi import APIRouter

from ...schemas.documents import Document
from ...services import documents_service

router = APIRouter()


@router.get("/", response_model=list[Document])
async def list_documents() -> Iterable[Document]:
    return list(documents_service.list_documents())
