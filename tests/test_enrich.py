"""Tests for description/tag extraction. Pure parsing — no network."""

import json

from goodreads_to_anki.enrich import parse_book_html

# A trimmed version of the JSON Goodreads embeds in __NEXT_DATA__.
_APOLLO = {
    "props": {
        "pageProps": {
            "apolloState": {
                "Book:kca://book/v1.X": {
                    "__typename": "Book",
                    "title": "Cthulhu'nun \u00c7a\u011fr\u0131s\u0131",
                    "description": "<p>Korku edebiyat\u0131n\u0131n ba\u015fyap\u0131t\u0131.</p>",
                    "bookGenres": [
                        {"genre": {"__ref": "Genre:kca://genre/horror"}},
                        {"genre": {"__ref": "Genre:kca://genre/fiction"}},
                        {"genre": {"name": "Classics"}},  # inline variant
                    ],
                },
                "Genre:kca://genre/horror": {"__typename": "Genre", "name": "Horror"},
                "Genre:kca://genre/fiction": {"__typename": "Genre", "name": "Fiction"},
            }
        }
    }
}


def _page(apollo: dict) -> str:
    return (
        '<html><head></head><body>'
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(apollo)
        + "</script></body></html>"
    )


def test_extracts_description_and_tags():
    desc, tags = parse_book_html(_page(_APOLLO))
    assert "ba\u015fyap\u0131t" in desc
    assert tags == ["Horror", "Fiction", "Classics"]


def test_meta_fallback_when_no_next_data():
    html = '<meta property="og:description" content="A fallback blurb.">'
    desc, tags = parse_book_html(html)
    assert desc == "A fallback blurb."
    assert tags == []


def test_handles_garbage_gracefully():
    desc, tags = parse_book_html("<html>no data here</html>")
    assert desc == ""
    assert tags == []


def test_ldjson_description_fallback():
    html = (
        '<script type="application/ld+json">'
        '{"@type":"Book","name":"X","description":"From JSON-LD."}'
        "</script>"
    )
    desc, tags = parse_book_html(html)
    assert desc == "From JSON-LD."


def test_genre_link_fallback():
    html = (
        '<div>Genres'
        '<a href="/genres/horror">Horror</a>'
        '<a href="/genres/classics">Classics</a>'
        '<a href="/genres/horror">Horror</a>'  # duplicate ignored
        "</div>"
    )
    _desc, tags = parse_book_html(html)
    assert tags == ["Horror", "Classics"]


def test_meta_is_html_unescaped():
    html = '<meta name="description" content="Tom &amp; Jerry">'
    desc, _tags = parse_book_html(html)
    assert desc == "Tom & Jerry"


def test_stats_summary_flags_blocking():
    from goodreads_to_anki.enrich import EnrichStats

    stats = EnrichStats(total=10, enriched=0, failed=10, first_error="HTTP 403")
    msg = stats.summary()
    assert "HTTP 403" in msg
    assert "blocking" in msg.lower()


def test_book_id_from_canonical():
    from goodreads_to_anki.enrich import _book_id_from_html

    # href-before-rel, the order browsers actually save
    html = '<link href="https://www.goodreads.com/en/book/show/5220293-x" rel="canonical">'
    assert _book_id_from_html(html) == "5220293"


def test_enrich_from_html_matches_by_id():
    import os
    import tempfile

    from goodreads_to_anki.enrich import enrich_from_html
    from goodreads_to_anki.models import Book

    page = (
        '<link rel="canonical" href="/book/show/5220293-x">'
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(_APOLLO)
        + "</script>"
    )
    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "saved.html"), "w", encoding="utf-8") as fh:
        fh.write(page)

    books = [Book(book_id="5220293", title="Match"), Book(book_id="999", title="Miss")]
    stats = enrich_from_html(books, folder)

    assert books[0].tags == ["Horror", "Fiction", "Classics"]
    assert "ba\u015fyap\u0131t" in books[0].description
    assert books[1].tags == []  # no saved page for this one
    assert stats.enriched == 1
    assert stats.missing == 1
