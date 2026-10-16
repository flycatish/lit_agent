from __future__ import annotations
from abc import ABC, abstractmethod

from core.types import Paper


class SourceBase(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[Paper]:
        ...

    def is_available(self) -> bool:
        return True
