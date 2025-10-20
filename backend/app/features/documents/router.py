from typing import Iterable

from fastapi import APIRouter

from .schemas import Document
from .service import list_documents as list_documents_service

router = APIRouter()


@router.get("/", response_model=list[Document])
async def list_documents() -> Iterable[Document]:
    return list(list_documents_service())
