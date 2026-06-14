"""Tests for the CSV source. These use only the standard library, so they run
without genanki or requests installed."""

from datetime import date
from pathlib import Path

from goodreads_to_anki.sources import CsvSource

SAMPLE = Path(__file__).parent / "sample_goodreads_export.csv"


def load():
    return CsvSource(SAMPLE).books()


def test_parses_all_rows():
    books = load()
    assert len(books) == 3


def test_typed_and_cleaned_fields():
    dune = load()[0]
    assert dune.title == "Dune"
    assert dune.author == "Frank Herbert"
    assert dune.isbn == "0441013597"          # Excel wrapper stripped
    assert dune.isbn13 == "9780441013593"
    assert dune.my_rating == 5
    assert dune.average_rating == 4.26
    assert dune.num_pages == 604
    assert dune.date_read == date(2019, 3, 14)
    assert dune.shelves == ["sci-fi", "favorites"]
    assert dune.is_read


def test_blank_and_missing_values():
    gatsby = load()[1]
    assert gatsby.date_read is None           # empty Date Read
    assert gatsby.my_rating == 0              # "0" means unrated
    assert not gatsby.is_read                 # to-read shelf

    hobbit = load()[2]
    assert hobbit.isbn == ""                  # empty ="" wrapper
    assert hobbit.num_pages is None           # blank page count
    assert hobbit.additional_authors == "Douglas A. Anderson"
    assert "Douglas A. Anderson" in hobbit.display_author


def test_stable_key_uses_book_id():
    dune = load()[0]
    assert dune.stable_key == "goodreads:11297"
    assert dune.goodreads_url.endswith("/book/show/11297")


def test_filter_only_read():
    read = CsvSource(SAMPLE).books(where=lambda b: b.is_read)
    assert {b.title for b in read} == {"Dune", "The Hobbit"}
