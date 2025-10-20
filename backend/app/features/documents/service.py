from typing import Iterable

from .repository import InMemoryDocumentsRepository
from .schemas import Document

_repo = InMemoryDocumentsRepository()


def list_documents() -> Iterable[Document]:
    return _repo.list()
