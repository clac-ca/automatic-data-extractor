from typing import Iterable, Optional

from app.shared.repositories.base import Repository

from .schemas import Document


class InMemoryDocumentsRepository(Repository[Document]):
    def __init__(self) -> None:
        self._documents = {}

    def list(self) -> Iterable[Document]:
        return self._documents.values()

    def get(self, item_id: str) -> Optional[Document]:
        return self._documents.get(item_id)
