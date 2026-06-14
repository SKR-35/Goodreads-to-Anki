# goodreads-to-anki

Turn your Goodreads library into an [Anki](https://apps.ankiweb.net/) deck — one
card per book, with your rating, review, shelves, cover image, and description.

## Why two data sources?

Goodreads **retired its public API in December 2020** and no longer issues keys
(old keys now return `403`), so there's no official programmatic endpoint. This
tool uses the two access paths that still work:

| Source | Best for | Has covers/descriptions? | Notes |
|--------|----------|--------------------------|-------|
| **CSV export** (`csv`) | your own full library | no | Official, reliable, every personal field |
| **RSS feed** (`rss`) | any public profile | yes | Unofficial, 100 books/page (auto-paginated) |

Both are exposed behind a common `BookSource` interface, so adding a third
source later (a scraper, OpenLibrary, etc.) only means writing one new class.

## Install

```bash
git clone SKR-35/Goodreads-to-Anki
cd goodreads-to-anki
pip install -e .
```

Requires Python 3.10+.

## Getting your data out of Goodreads (CSV)

1. Go to **My Books**.
2. In the left sidebar under *Tools*, click **Import and Export**.
3. Click **Export Library** and download `goodreads_library_export.csv`.

## Usage

From your CSV export (recommended), only the books you've actually read:

```bash
goodreads-to-anki csv --input goodreads_library_export.csv \
    --only-read --output read.apkg
```

From any public profile's RSS feed, with cover images embedded (the user id is
the number in their profile URL, `goodreads.com/user/show/<id>-name`):

```bash
goodreads-to-anki rss --user-id 12345678 --shelf read --covers \
    --output friend.apkg
```

Then in Anki: **File → Import** and pick the `.apkg`.

### Card layout

- **Front:** a table of your Goodreads fields (Book Id, Title, Author, Author
  l-f, ISBN, My Rating, Publisher, Pages, dates, shelves, review, …). Rows with
  no value are hidden automatically.
- **Back:** the book **description** and **genre tags** scraped from the book's
  Goodreads page, plus a link to it.

### Description + tags (`--enrich`)

The CSV export and RSS feed don't include genre tags (and the CSV has no
description), so those come from each book's Goodreads page. Add `--enrich`:

```bash
goodreads-to-anki csv --input goodreads_library_export.csv --enrich -o read.apkg
```

This makes one polite request per book (tune the gap with `--enrich-delay`,
default 1s) using a normal browser User-Agent, and prints per-item progress
plus a final status line:

```
[ 1/100] Philosophical Investigations ... ok (10 tags)
[ 2/100] Candide ... ok (8 tags)
[enrich] 100/100 books got a description and/or tags
```

It's best-effort: any book that can't be fetched or parsed just ships without
a description/tags.

#### If Goodreads blocks the live fetch

Goodreads sits behind Cloudflare, which blocks plain HTTP libraries, so plain
`--enrich` often reports `HTTP 403`/`429` and brings back nothing. Two reliable
ways around it:

**A) A real browser (`--enrich-browser`)** — drives Firefox via Selenium, so
the page loads like a human's and Cloudflare lets it through. Install the extra
once (and have Firefox installed):

```bash
pip install "goodreads-to-anki[browser]"     # selenium + webdriver-manager
```

```bash
goodreads-to-anki csv --input goodreads_library_export.csv \
    --enrich-browser --headless true -o read.apkg
```

- `--headless true|false` — run the browser invisibly (`true`, default) or show
  the window (`false`). Use `false` the first time if you need to click through
  a Cloudflare/login prompt.
- `--firefox-profile PATH` — reuse one of your Firefox profiles so it inherits
  your cookies and an already-passed Cloudflare challenge (most reliable). Find
  the path at `about:profiles` in Firefox.

```bash
goodreads-to-anki csv --input library.csv --enrich-browser --headless false \
    --firefox-profile "C:/Users/you/AppData/Roaming/Mozilla/Firefox/Profiles/xxxx.default-release"
```

**B) Saved HTML pages (`--enrich-html`)** — save the book pages from your
browser (File → Save Page As → "Webpage, HTML Only") into a folder, then:

```bash
goodreads-to-anki csv --input goodreads_library_export.csv \
    --enrich-html ./saved_pages -o read.apkg
```

Each saved `.htm`/`.html` is matched to a book by the Goodreads id in its
canonical URL, so filenames don't matter and unmatched books just skip
(`... no saved page`). This never touches the network.

Without any `--enrich*` flag, the back simply omits the description and tags.

### Useful flags

- `--only-read` — only books on the *read* shelf
- `--only-rated` — only books you gave a star rating
- `--limit N` — stop after N books (handy while testing)
- `--deck-name "My Books"` — name the deck
- `--shelf to-read` (rss) — any shelf, not just *read*

## Use it as a library

```python
from goodreads_to_anki.config import ExportConfig
from goodreads_to_anki.pipeline import run

run(ExportConfig(
    source="csv",
    input_path="goodreads_library_export.csv",
    only_read=True,
    output_path="read.apkg",
))
```

Or wire the pieces yourself for full control:

```python
from goodreads_to_anki.sources import CsvSource
from goodreads_to_anki.anki import AnkiExporter

books = CsvSource("library.csv").books(where=lambda b: b.my_rating >= 4)
AnkiExporter(deck_name="Favourites").export(books, "favourites.apkg")
```

### Custom card design

The card layout is a swappable `CardStyle` (front template, back template,
CSS). Pass your own to restyle the whole deck — see
`goodreads_to_anki/anki/card_templates.py` for the default and the available
`{{Field}}` names.

```python
from goodreads_to_anki.anki import AnkiExporter, CardStyle

minimal = CardStyle(
    name="Minimal",
    front="{{Title}}",
    back="{{FrontSide}}<hr>by {{Author}} — {{Rating}}",
    css=".card { font-family: sans-serif; }",
)
AnkiExporter(style=minimal).export(books, "minimal.apkg")
```

## Project layout

```
goodreads_to_anki/
├── models.py            # Book dataclass (pure data, source-agnostic)
├── config.py            # ExportConfig
├── pipeline.py          # source -> filter -> enrich -> covers -> exporter
├── cli.py               # argparse front end
├── covers.py            # optional cover-image downloader
├── enrich.py            # description + tags from a live page OR saved HTML
├── browser.py           # description + tags via real Firefox (Selenium)
├── sources/
│   ├── base.py          # BookSource interface
│   ├── csv_source.py    # Goodreads CSV export (stdlib only)
│   └── rss_source.py    # Goodreads RSS feed (paginated)
└── anki/
    ├── card_templates.py # note fields + default CardStyle
    └── exporter.py       # genanki -> .apkg
```

## Notes & limits

- Re-importing an updated deck **updates** existing cards rather than
  duplicating them (each note's GUID is derived from the Goodreads book id).
- `--enrich` scrapes public book pages for the description and genre tags.
  It's best-effort and may need updating if Goodreads changes their page
  markup. Keep it to modest personal use and respect Goodreads' Terms.
- The RSS feed exposes fewer private fields than the CSV (e.g. private notes
  aren't included) and only public profiles are readable.
- Respect Goodreads' Terms of Service and don't hammer the RSS feed.