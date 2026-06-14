"""The :class:`BookSource` interface that every reader implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Iterable, Iterator, List, Optional

from ..models import Book

# A predicate used to filter books, e.g. ``lambda b: b.is_read``.
BookFilter = Callable[[Book], bool]


class BookSource(ABC):
    """Reads books from somewhere and yields :class:`Book` objects.

    Sources are iterables, so you can write ``for book in source: ...`` or
    materialise everything with ``source.books()``.
    """

    #: Human-readable source name, handy for logging.
    name: str = "source"

    @abstractmethod
    def fetch(self) -> Iterator[Book]:
        """Yield books one at a time. Implemented by each subclass."""
        raise NotImplementedError

    def books(self, where: Optional[BookFilter] = None) -> List[Book]:
        """Return all books as a list, optionally filtered by ``where``."""
        items: Iterable[Book] = self.fetch()
        if where is not None:
            return [b for b in items if where(b)]
        return list(items)

    def __iter__(self) -> Iterator[Book]:
        return self.fetch()
