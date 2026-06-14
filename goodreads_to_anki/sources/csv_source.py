"""Read books from a Goodreads CSV library export.

This is the most reliable source: it's the only *official* way left to get
your data out of Goodreads (the public API was retired in 2020). Export your
library from Goodreads: **My Books → (Tools, left sidebar) Import and Export
→ Export Library**, then point this source at the downloaded file.

The export contains every personal field: your rating, review, private notes,
shelves, date read/added, page counts, etc. It does *not* contain cover
images or descriptions — use :class:`~goodreads_to_anki.sources.RssSource`
if you want those.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterator, Union

from .._util import clean_isbn, parse_date, parse_float, parse_int, split_shelves
from ..models import Book
from .base import BookSource

# Maps a Goodreads CSV column header -> Book attribute, for the simple
# string-valued columns. Typed columns are handled explicitly below.
_STRING_COLUMNS = {
    "Book Id": "book_id",
    "Title": "title",
    "Author": "author",
    "Author l-f": "author_lf",
    "Additional Authors": "additional_authors",
    "Publisher": "publisher",
    "Binding": "binding",
    "Exclusive Shelf": "exclusive_shelf",
    "Bookshelves with positions": "bookshelves_with_positions",
    "My Review": "my_review",
    "Spoiler": "spoiler",
    "Private Notes": "private_notes",
}


class CsvSource(BookSource):
    """Parse a Goodreads library export (``goodreads_library_export.csv``)."""

    name = "goodreads-csv"

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Goodreads CSV not found: {self.path}")

    def fetch(self) -> Iterator[Book]:
        # newline="" is required by the csv module; Goodreads uses UTF-8.
        with self.path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield self._row_to_book(row)

    @staticmethod
    def _row_to_book(row: Dict[str, str]) -> Book:
        book = Book()
        for column, attr in _STRING_COLUMNS.items():
            setattr(book, attr, (row.get(column) or "").strip())

        book.isbn = clean_isbn(row.get("ISBN"))
        book.isbn13 = clean_isbn(row.get("ISBN13"))
        book.my_rating = parse_int(row.get("My Rating")) or 0
        book.average_rating = parse_float(row.get("Average Rating"))
        book.num_pages = parse_int(row.get("Number of Pages"))
        book.year_published = parse_int(row.get("Year Published"))
        book.original_publication_year = parse_int(row.get("Original Publication Year"))
        book.date_read = parse_date(row.get("Date Read"))
        book.date_added = parse_date(row.get("Date Added"))
        book.shelves = split_shelves(row.get("Bookshelves"))
        book.read_count = parse_int(row.get("Read Count")) or 0
        book.owned_copies = parse_int(row.get("Owned Copies")) or 0
        return book
