"""Card styling for the generated Anki notes.

Front: a table of the Goodreads CSV fields. Rows whose value is empty are
hidden automatically (each row is wrapped in an Anki ``{{#Field}}`` block and
the exporter renders empty/zero values as blank strings).

Back: the book description and genre tags pulled from the Goodreads page
(see ``goodreads_to_anki.enrich``), plus the Goodreads link.

The note's field *names* are fixed (see :data:`NOTE_FIELDS`) so that the
exporter and the templates stay in sync. To restyle the deck, pass a different
:class:`CardStyle` to :class:`~goodreads_to_anki.anki.exporter.AnkiExporter`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

#: Ordered list of Anki note fields. The exporter fills these in this order.
#: Each tuple is (field_name, human_label_shown_in_the_table).
FRONT_FIELDS: List[Tuple[str, str]] = [
    ("BookId", "Book Id"),
    ("Title", "Title"),
    ("Author", "Author"),
    ("AuthorLF", "Author l-f"),
    ("AdditionalAuthors", "Additional Authors"),
    ("ISBN", "ISBN"),
    ("ISBN13", "ISBN13"),
    ("MyRating", "My Rating"),
    ("Publisher", "Publisher"),
    ("Binding", "Binding"),
    ("NumberOfPages", "Number of Pages"),
    ("YearPublished", "Year Published"),
    ("OriginalPublicationYear", "Original Publication Year"),
    ("DateRead", "Date Read"),
    ("DateAdded", "Date Added"),
    ("Bookshelves", "Bookshelves"),
    ("BookshelvesWithPositions", "Bookshelves with positions"),
    ("ExclusiveShelf", "Exclusive Shelf"),
    ("MyReview", "My Review"),
    ("Spoiler", "Spoiler"),
    ("PrivateNotes", "Private Notes"),
    ("ReadCount", "Read Count"),
    ("OwnedCopies", "Owned Copies"),
]

#: Back-of-card fields (the two scraped fields plus the link).
BACK_FIELDS: List[str] = ["Description", "Tags", "GoodreadsUrl"]

#: The full ordered field list the exporter must produce values for.
NOTE_FIELDS: List[str] = [name for name, _ in FRONT_FIELDS] + BACK_FIELDS


@dataclass(frozen=True)
class CardStyle:
    """A named bundle of front template, back template and CSS."""

    name: str
    front: str
    back: str
    css: str


def _build_front() -> str:
    rows = "\n".join(
        f'    {{{{#{name}}}}}<tr><th>{label}</th><td>{{{{{name}}}}}</td></tr>{{{{/{name}}}}}'
        for name, label in FRONT_FIELDS
    )
    return (
        '<div class="gr-front">\n'
        '  <table class="gr-table">\n'
        f"{rows}\n"
        "  </table>\n"
        "</div>"
    )


_FRONT = _build_front()

_BACK = """
{{FrontSide}}
<hr id="answer">
<div class="gr-back">
  {{#Description}}<div class="block"><span class="label">Description</span>
    <div class="desc">{{Description}}</div></div>{{/Description}}
  {{#Tags}}<div class="block"><span class="label">Tags</span>
    <div class="tags">{{Tags}}</div></div>{{/Tags}}
  {{#GoodreadsUrl}}<div class="link"><a href="{{GoodreadsUrl}}">View on Goodreads</a></div>{{/GoodreadsUrl}}
</div>
""".strip()

_CSS = """
.card { background: #fbfaf7; color: #2c2a26;
        font-family: -apple-system, Segoe UI, Roboto, sans-serif; }
.gr-front { max-width: 680px; margin: 0 auto; }
.gr-table { width: 100%; border-collapse: collapse; font-size: .92em; }
.gr-table th, .gr-table td { text-align: left; vertical-align: top;
        padding: 6px 10px; border-bottom: 1px solid #ece8df; }
.gr-table th { width: 38%; color: #6f6a5e; font-weight: 600;
        white-space: nowrap; }
.gr-table td { color: #2c2a26; }
#answer { border: none; border-top: 1px solid #e3ddcf; margin: 16px 0; }
.gr-back { max-width: 680px; margin: 0 auto; }
.block { text-align: left; margin: 12px 0; padding: 10px 14px;
        background: #fff; border: 1px solid #ece8df; border-radius: 8px; }
.label { display: block; font-variant: small-caps; letter-spacing: .04em;
        color: #b04a3a; font-weight: bold; margin-bottom: 6px; }
.desc { line-height: 1.5; }
.tags { line-height: 2; }
.tag { display: inline-block; padding: 2px 10px; margin: 2px 4px 2px 0;
        background: #eef2ec; border: 1px solid #d5ddce; border-radius: 999px;
        font-size: .85em; color: #41553c; }
.link { margin-top: 10px; font-size: .9em; }
""".strip()


#: The card style used unless you supply your own.
DEFAULT_STYLE = CardStyle(name="Table", front=_FRONT, back=_BACK, css=_CSS)
