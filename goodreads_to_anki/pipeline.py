"""High-level orchestration: config in, ``.apkg`` out.

This is the seam most users will call from their own scripts:

    from goodreads_to_anki.config import ExportConfig
    from goodreads_to_anki.pipeline import run

    run(ExportConfig(source="csv", input_path="library.csv"))
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import List

from .anki.exporter import AnkiExporter
from .config import ExportConfig
from .models import Book
from .sources import CsvSource
from .sources.base import BookSource


def build_source(config: ExportConfig) -> BookSource:
    """Construct the right :class:`BookSource` for the config."""
    if config.source == "csv":
        if not config.input_path:
            raise ValueError("source='csv' requires input_path")
        return CsvSource(config.input_path)
    if config.source == "rss":
        if not config.user_id:
            raise ValueError("source='rss' requires user_id")
        from .sources import RssSource  # lazy: needs `requests`

        return RssSource(config.user_id, shelf=config.shelf, per_page=config.per_page)
    raise ValueError(f"Unknown source: {config.source!r}")


def select_books(config: ExportConfig, source: BookSource) -> List[Book]:
    """Apply the config's filters and limit to the source's books."""
    books: List[Book] = []
    for book in source:
        if config.only_read and not book.is_read:
            continue
        if config.only_rated and not book.my_rating:
            continue
        books.append(book)
        if config.limit and len(books) >= config.limit:
            break
    return books


def _make_progress_printer():
    """Return an on_progress callback that prints '[i/N] Title ... status'."""
    labels = {
        "ok": "ok",
        "no_data": "no data",
        "error": "error",
        "missing": "no saved page",
    }

    def progress(index: int, total: int, book, status: str, detail: str) -> None:
        width = len(str(total))
        title = (book.title or book.book_id or "?")[:50]
        line = f"[{index:>{width}}/{total}] {title} ... {labels.get(status, status)}"
        if detail:
            line += f" ({detail})"
        print(line, file=sys.stderr)

    return progress


def run(config: ExportConfig) -> Path:
    """Execute a full export and return the path to the written ``.apkg``."""
    source = build_source(config)
    books = select_books(config, source)
    if not books:
        raise ValueError("No books matched — check the source and filters.")

    if config.enrich_html or config.enrich_browser or config.enrich:
        progress = _make_progress_printer()
        if config.enrich_html:
            from .enrich import enrich_from_html  # lazy

            stats = enrich_from_html(
                books, config.enrich_html, on_progress=progress
            )
        elif config.enrich_browser:
            from .browser import enrich_books_browser  # lazy: needs selenium

            stats = enrich_books_browser(
                books,
                headless=config.headless,
                profile_path=config.firefox_profile,
                delay=config.enrich_delay,
                on_progress=progress,
            )
        else:
            from .enrich import enrich_books  # lazy: needs `requests`

            stats = enrich_books(
                books, delay=config.enrich_delay, on_progress=progress
            )
        print(stats.summary(), file=sys.stderr)

    media_files: List[str] = []
    if config.download_covers:
        from .covers import download_covers  # lazy: needs `requests`

        media_dir = Path(tempfile.mkdtemp(prefix="gr_covers_"))
        media_files = download_covers(books, media_dir)

    exporter = AnkiExporter(deck_name=config.resolved_deck_name())
    return exporter.export(books, config.output_path, media_files=media_files)
