from abc import ABC, abstractmethod
from typing import Generic, Iterable, Optional, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """
    Base repository abstraction.
    Concrete repositories should implement persistence-specific logic.
    """

    @abstractmethod
    def list(self) -> Iterable[T]:
        raise NotImplementedError

    @abstractmethod
    def get(self, item_id: str) -> Optional[T]:
        raise NotImplementedError
