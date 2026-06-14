"""Test the Selenium browser-enrichment flow using a fake driver, so it runs
without Selenium or a real browser installed."""

import json

from goodreads_to_anki.browser import enrich_books_browser
from goodreads_to_anki.models import Book

_APOLLO = {
    "props": {
        "pageProps": {
            "apolloState": {
                "Book:1": {
                    "__typename": "Book",
                    "description": "<p>Korku \u015faheseri.</p>",
                    "bookGenres": [
                        {"genre": {"__ref": "Genre:h"}},
                        {"genre": {"name": "Classics"}},
                    ],
                },
                "Genre:h": {"__typename": "Genre", "name": "Horror"},
            }
        }
    }
}

_PAGE = (
    '<script id="__NEXT_DATA__" type="application/json">'
    + json.dumps(_APOLLO)
    + "</script>"
)


class FakeDriver:
    """Minimal stand-in for a Selenium WebDriver."""

    def __init__(self, html: str):
        self._html = html
        self.visited = []

    def get(self, url: str):
        self.visited.append(url)

    @property
    def page_source(self) -> str:
        return self._html


def test_browser_enrich_with_injected_driver():
    books = [Book(book_id="5220293", title="Match"), Book(book_id="", title="NoId")]
    driver = FakeDriver(_PAGE)

    # settle=0 avoids real sleeps; driver injection avoids launching Firefox.
    stats = enrich_books_browser(books, delay=0, settle=0, driver=driver)

    assert books[0].tags == ["Horror", "Classics"]
    assert "\u015faheseri" in books[0].description
    assert stats.total == 1          # the empty-id book is skipped
    assert stats.enriched == 1
    assert driver.visited == ["https://www.goodreads.com/book/show/5220293"]


def test_browser_progress_callbacks():
    seen = []
    enrich_books_browser(
        [Book(book_id="1", title="A")],
        delay=0,
        settle=0,
        driver=FakeDriver(_PAGE),
        on_progress=lambda i, n, b, status, detail: seen.append((i, n, status)),
    )
    assert seen == [(1, 1, "ok")]
