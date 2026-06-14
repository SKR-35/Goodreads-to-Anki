"""The :class:`Book` domain model.

This is intentionally a *pure* data container: it knows nothing about CSV
columns, RSS XML, or Anki. Each source is responsible for mapping its own
format onto these fields, which keeps the model reusable and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass(slots=True)
class Book:
    """A single book together with the reader's relationship to it.

    Fields up to ``owned_copies`` map onto the Goodreads CSV export columns.
    ``description``, ``cover_url`` and ``cover_filename`` are only populated
    by the RSS source (the CSV export does not include them).
    """

    book_id: str = ""
    title: str = ""
    author: str = ""
    author_lf: str = ""
    additional_authors: str = ""
    isbn: str = ""
    isbn13: str = ""
    my_rating: int = 0
    average_rating: Optional[float] = None
    publisher: str = ""
    binding: str = ""
    num_pages: Optional[int] = None
    year_published: Optional[int] = None
    original_publication_year: Optional[int] = None
    date_read: Optional[date] = None
    date_added: Optional[date] = None
    shelves: List[str] = field(default_factory=list)
    exclusive_shelf: str = ""
    bookshelves_with_positions: str = ""
    my_review: str = ""
    spoiler: str = ""
    private_notes: str = ""
    read_count: int = 0
    owned_copies: int = 0

    # --- Extra fields, only available from the RSS source or enrichment ---
    description: str = ""
    tags: List[str] = field(default_factory=list)  # genres, from the book page
    cover_url: str = ""
    cover_filename: str = ""  # set once a cover image is downloaded locally

    # --- Derived convenience properties -----------------------------------
    @property
    def goodreads_url(self) -> str:
        if not self.book_id:
            return ""
        return f"https://www.goodreads.com/book/show/{self.book_id}"

    @property
    def display_author(self) -> str:
        """Author plus any additional authors, nicely joined."""
        if self.additional_authors:
            return f"{self.author}, {self.additional_authors}"
        return self.author

    @property
    def is_read(self) -> bool:
        return self.exclusive_shelf == "read" or "read" in self.shelves

    @property
    def stable_key(self) -> str:
        """A stable identity used to de-duplicate Anki notes across runs."""
        if self.book_id:
            return f"goodreads:{self.book_id}"
        return f"goodreads:{self.title}::{self.author}".lower()

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        author = f" — {self.author}" if self.author else ""
        return f"{self.title}{author}"
