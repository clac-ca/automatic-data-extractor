from typing import Iterable

from ..repositories.documents_repo import InMemoryDocumentsRepository
from ..schemas.documents import Document

_repo = InMemoryDocumentsRepository()


def list_documents() -> Iterable[Document]:
    return _repo.list()
