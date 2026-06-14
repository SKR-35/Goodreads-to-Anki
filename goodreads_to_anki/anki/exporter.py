"""Turn :class:`~goodreads_to_anki.models.Book` objects into an Anki ``.apkg``.

Built on `genanki <https://github.com/kerrickstaley/genanki>`_. Each book maps
to one note whose GUID is derived from the Goodreads id, so re-importing an
updated deck *updates* existing cards instead of creating duplicates.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

import genanki

from ..models import Book
from .card_templates import DEFAULT_STYLE, NOTE_FIELDS, CardStyle

# Fixed, arbitrary-but-stable ids. genanki requires these to be constant
# across runs so that Anki recognises the same model/deck on re-import.
_MODEL_ID = 1_738_261_901
_DECK_ID = 2_059_400_110


class AnkiExporter:
    """Build and write an Anki package from a collection of books."""

    def __init__(
        self,
        deck_name: str = "Goodreads",
        style: CardStyle = DEFAULT_STYLE,
        *,
        model_id: int = _MODEL_ID,
        deck_id: int = _DECK_ID,
    ) -> None:
        self.deck_name = deck_name
        self.style = style
        self._model = genanki.Model(
            model_id,
            f"Goodreads Book ({style.name})",
            fields=[{"name": name} for name in NOTE_FIELDS],
            templates=[{"name": "Card 1", "qfmt": style.front, "afmt": style.back}],
            css=style.css,
        )
        self._deck = genanki.Deck(deck_id, deck_name)

    # ------------------------------------------------------------------
    def add(self, book: Book) -> None:
        self._deck.add_note(
            genanki.Note(
                model=self._model,
                fields=self._book_to_fields(book),
                guid=genanki.guid_for(book.stable_key),
            )
        )

    def export(
        self,
        books: Iterable[Book],
        output_path: Union[str, Path],
        media_files: Optional[Sequence[Union[str, Path]]] = None,
    ) -> Path:
        """Add every book and write the ``.apkg`` to ``output_path``."""
        count = 0
        for book in books:
            self.add(book)
            count += 1
        if count == 0:
            raise ValueError("No books to export — nothing was written.")

        package = genanki.Package(self._deck)
        if media_files:
            package.media_files = [str(p) for p in media_files]
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        package.write_to_file(str(output_path))
        return output_path

    # ------------------------------------------------------------------
    @staticmethod
    def _book_to_fields(book: Book) -> List[str]:
        """Map a Book onto the ordered :data:`NOTE_FIELDS` as HTML strings.

        Empty / zero values become ``""`` so that the table rows (and the
        description/tags blocks) hide themselves via Anki's ``{{#Field}}``
        conditionals.
        """

        def esc(value: object) -> str:
            return html.escape(str(value)) if value not in (None, "", 0) else ""

        def num(value: object) -> str:
            return str(value) if value else ""  # 0 / None -> hidden

        def dt(value) -> str:
            return value.strftime("%Y/%m/%d") if value else ""

        tags_html = " ".join(
            f'<span class="tag">{html.escape(t)}</span>' for t in book.tags
        )

        # Plain-text fields are escaped; review/notes/description keep any
        # HTML that Goodreads stored (e.g. <br> line breaks).
        values = {
            "BookId": esc(book.book_id),
            "Title": esc(book.title),
            "Author": esc(book.author),
            "AuthorLF": esc(book.author_lf),
            "AdditionalAuthors": esc(book.additional_authors),
            "ISBN": esc(book.isbn),
            "ISBN13": esc(book.isbn13),
            "MyRating": num(book.my_rating),
            "Publisher": esc(book.publisher),
            "Binding": esc(book.binding),
            "NumberOfPages": num(book.num_pages),
            "YearPublished": num(book.year_published),
            "OriginalPublicationYear": num(book.original_publication_year),
            "DateRead": esc(dt(book.date_read)),
            "DateAdded": esc(dt(book.date_added)),
            "Bookshelves": esc(", ".join(book.shelves)),
            "BookshelvesWithPositions": esc(book.bookshelves_with_positions),
            "ExclusiveShelf": esc(book.exclusive_shelf),
            "MyReview": book.my_review or "",
            "Spoiler": esc(book.spoiler),
            "PrivateNotes": esc(book.private_notes),
            "ReadCount": num(book.read_count),
            "OwnedCopies": num(book.owned_copies),
            "Description": book.description or "",
            "Tags": tags_html,
            "GoodreadsUrl": esc(book.goodreads_url),
        }
        return [values[name] for name in NOTE_FIELDS]
