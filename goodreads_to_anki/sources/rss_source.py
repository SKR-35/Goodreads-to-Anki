"""Read books from a public Goodreads shelf RSS feed.

Useful when you don't have a CSV export but the profile is public. Works for
*any* user via their numeric Goodreads id. Unlike the CSV export, the feed
includes a book description and cover image URLs — but it omits private fields
(review/notes are partial) and each feed page is capped at 100 items, so we
paginate.

Find a user id in their profile URL: ``goodreads.com/user/show/<id>-name``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterator, Optional

import requests

from .._util import parse_date, parse_float, parse_int, split_shelves
from ..models import Book
from .base import BookSource

_FEED_URL = "https://www.goodreads.com/review/list_rss/{user_id}"
_DEFAULT_HEADERS = {"User-Agent": "goodreads-to-anki/0.1 (+https://github.com/)"}
_MAX_PAGES = 100  # safety guard against infinite loops


class RssSource(BookSource):
    """Fetch and parse a Goodreads shelf RSS feed, following pagination."""

    name = "goodreads-rss"

    def __init__(
        self,
        user_id: str,
        shelf: str = "read",
        per_page: int = 100,
        *,
        timeout: float = 30.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.user_id = str(user_id).strip()
        self.shelf = shelf
        self.per_page = per_page
        self.timeout = timeout
        self._session = session or requests.Session()

    def fetch(self) -> Iterator[Book]:
        page = 1
        while page <= _MAX_PAGES:
            items = list(self._fetch_page(page))
            if not items:
                break
            yield from items
            if len(items) < self.per_page:
                break  # last (partial) page reached
            page += 1

    # ------------------------------------------------------------------
    def _fetch_page(self, page: int) -> Iterator[Book]:
        params = {"shelf": self.shelf, "per_page": self.per_page, "page": page}
        resp = self._session.get(
            _FEED_URL.format(user_id=self.user_id),
            params=params,
            headers=_DEFAULT_HEADERS,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.iterfind(".//item"):
            yield self._item_to_book(item)

    def _item_to_book(self, item: ET.Element) -> Book:
        def text(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""

        cover = text("book_large_image_url") or text("book_image_url")
        book = Book(
            book_id=text("book_id"),
            title=text("title"),
            author=text("author_name"),
            isbn=text("isbn"),
            my_rating=parse_int(text("user_rating")) or 0,
            average_rating=parse_float(text("average_rating")),
            year_published=parse_int(text("book_published")),
            date_read=parse_date(text("user_read_at")),
            date_added=parse_date(text("user_date_added") or text("pubDate")),
            shelves=split_shelves(text("user_shelves")),
            exclusive_shelf=self.shelf,
            my_review=text("user_review"),
            description=text("book_description"),
            cover_url=cover,
        )
        # The <book> child sometimes carries the page count.
        book_el = item.find("book")
        if book_el is not None:
            book.num_pages = parse_int((book_el.findtext("num_pages") or ""))
        return book
