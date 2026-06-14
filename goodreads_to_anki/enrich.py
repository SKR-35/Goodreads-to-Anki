"""Fill in a book's *description* and *genre tags* from its Goodreads page.

Neither the CSV export nor the RSS feed includes genre tags, and the CSV has
no description either, so this enricher reads the public book page
(``https://www.goodreads.com/book/show/<book_id>``) and extracts both.

This is **opt-in** (pass ``--enrich`` on the CLI) and **best-effort**:
failures are reported (not hidden), requests are spaced out to be polite, and
Goodreads can change their page markup at any time. Respect Goodreads' Terms
of Service and keep this to your own modest, personal use.

Parsing tries several strategies, most reliable first, so it keeps working
even when one of them breaks:

1. Any embedded JSON blob that looks like an Apollo cache -> Book.description
   and Book.bookGenres (the genre tags).
2. JSON-LD (``application/ld+json``) -> description.
3. Plain-HTML fallbacks: ``/genres/...`` links for tags, the ``<meta>``
   description for the blurb.
"""

from __future__ import annotations

import html as _html
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Optional, Tuple, Union

import requests

from .models import Book

_URL = "https://www.goodreads.com/book/show/{book_id}"

# A realistic browser User-Agent: a bot-looking UA gets blocked by Goodreads.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_RETRY_STATUSES = {403, 429, 500, 502, 503}

_SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)
_META_DESC = re.compile(
    r'<meta\s+(?:property|name)="(?:og:description|description)"\s+content="([^"]*)"'
)
_GENRE_LINK = re.compile(r'href="/genres/[^"]+"[^>]*>([^<]+)</a>')

ErrorHandler = Callable[[Book, Exception], None]
# on_progress(index, total, book, status, detail); status in
# {"ok", "no_data", "error", "missing"}.
ProgressHandler = Callable[[int, int, Book, str, str], None]


@dataclass
class EnrichStats:
    """Outcome of an enrichment run, so the caller can report it."""

    total: int = 0          # books with a usable book_id
    enriched: int = 0       # books that gained a description and/or tags
    failed: int = 0         # requests that errored out
    missing: int = 0        # (local mode) no saved page matched the book
    first_error: str = ""

    def summary(self) -> str:
        if self.total == 0:
            return "[enrich] no books had a Goodreads id to look up."
        msg = f"[enrich] {self.enriched}/{self.total} books got a description and/or tags"
        if self.failed:
            msg += f"; {self.failed} request(s) failed (first: {self.first_error})"
            if self.enriched == 0:
                msg += (
                    ". Goodreads may be blocking automated requests from this "
                    "network — try again later, raise --enrich-delay, or use "
                    "--enrich-html with saved pages (see the README)."
                )
        if self.missing:
            msg += f"; {self.missing} had no matching saved page"
        return msg


def enrich_books(
    books: Iterable[Book],
    *,
    delay: float = 1.0,
    timeout: float = 30.0,
    overwrite_description: bool = False,
    session: Optional[requests.Session] = None,
    on_error: Optional[ErrorHandler] = None,
    on_progress: Optional[ProgressHandler] = None,
) -> EnrichStats:
    """Populate ``description`` and ``tags`` on each book, in place, by
    fetching each book's Goodreads page.

    ``delay`` seconds are slept between page requests. An existing description
    (e.g. from the RSS source) is kept unless ``overwrite_description`` is set.
    ``on_progress`` is called once per book so callers can show "i/N … ok".
    Returns an :class:`EnrichStats` describing what happened.
    """
    session = session or requests.Session()
    targets = [b for b in books if b.book_id]
    total = len(targets)
    stats = EnrichStats(total=total)
    for index, book in enumerate(targets, start=1):
        if index > 1 and delay:
            time.sleep(delay)
        try:
            description, tags = fetch_book_page(
                book.book_id, session=session, timeout=timeout
            )
        except Exception as exc:  # network / parse errors must not abort
            stats.failed += 1
            if not stats.first_error:
                stats.first_error = _short_error(exc)
            if on_error is not None:
                on_error(book, exc)
            _report(on_progress, index, total, book, "error", _short_error(exc))
            continue
        if _apply(book, description, tags, overwrite_description):
            stats.enriched += 1
            _report(on_progress, index, total, book, "ok", _detail(tags))
        else:
            _report(on_progress, index, total, book, "no_data", "")
    return stats


def enrich_from_html(
    books: Iterable[Book],
    paths: Union[str, Path, Iterable[Union[str, Path]]],
    *,
    overwrite_description: bool = False,
    on_progress: Optional[ProgressHandler] = None,
) -> EnrichStats:
    """Enrich books from **saved** Goodreads HTML pages instead of fetching.

    ``paths`` may be a single ``.htm``/``.html`` file, a directory of them, or
    a list. Each file is matched to a book by the Goodreads id in its canonical
    URL, so filenames don't matter. This never touches the network, so it works
    even when Goodreads blocks automated requests.
    """
    by_id: dict[str, Tuple[str, List[str]]] = {}
    for path in _expand_html_paths(paths):
        try:
            book_id, description, tags = parse_saved_page(path)
        except OSError:
            continue
        if book_id:
            by_id[book_id] = (description, tags)

    targets = [b for b in books if b.book_id]
    total = len(targets)
    stats = EnrichStats(total=total)
    for index, book in enumerate(targets, start=1):
        data = by_id.get(str(book.book_id))
        if data is None:
            stats.missing += 1
            _report(on_progress, index, total, book, "missing", "")
            continue
        description, tags = data
        if _apply(book, description, tags, overwrite_description):
            stats.enriched += 1
            _report(on_progress, index, total, book, "ok", _detail(tags))
        else:
            _report(on_progress, index, total, book, "no_data", "")
    return stats


def _apply(book: Book, description: str, tags: List[str], overwrite: bool) -> bool:
    gained = False
    if tags:
        book.tags = tags
        gained = True
    if description and (overwrite or not book.description):
        book.description = description
        gained = True
    return gained


def _report(handler, index, total, book, status, detail) -> None:
    if handler is not None:
        handler(index, total, book, status, detail)


def _detail(tags: List[str]) -> str:
    return f"{len(tags)} tags" if tags else "description only"


def parse_saved_page(path: Union[str, Path]) -> Tuple[str, str, List[str]]:
    """Read one saved page and return ``(book_id, description, tags)``."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    book_id = _book_id_from_html(text)
    description, tags = parse_book_html(text)
    return book_id, description, tags


def _expand_html_paths(
    paths: Union[str, Path, Iterable[Union[str, Path]]]
) -> List[Path]:
    if isinstance(paths, (str, Path)):
        paths = [paths]
    out: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for pattern in ("*.htm", "*.html", "*.HTM", "*.HTML"):
                out.extend(sorted(p.glob(pattern)))
        elif p.exists():
            out.append(p)
    return out


def fetch_book_page(
    book_id: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: float = 30.0,
    retries: int = 2,
    backoff: float = 2.0,
) -> Tuple[str, List[str]]:
    """Fetch one book page and return ``(description, tags)``.

    Retries a few times on the statuses Goodreads uses when throttling.
    """
    session = session or requests.Session()
    url = _URL.format(book_id=book_id)
    last: Optional[requests.Response] = None
    for attempt in range(retries + 1):
        last = session.get(url, headers=_HEADERS, timeout=timeout)
        if last.status_code in _RETRY_STATUSES and attempt < retries:
            time.sleep(backoff * (attempt + 1))
            continue
        last.raise_for_status()
        return parse_book_html(last.text)
    # Exhausted retries on a retryable status -> raise the last one.
    last.raise_for_status()  # type: ignore[union-attr]
    return "", []  # unreachable, keeps type-checkers happy


def parse_book_html(html_text: str) -> Tuple[str, List[str]]:
    """Extract ``(description, tags)`` from a Goodreads book page's HTML.

    Pure (no I/O), so it can be unit-tested without the network.
    """
    description, tags = "", []
    for blob in _json_blobs(html_text):
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        apollo = _find_apollo(data)
        if apollo is not None:
            d, t = _extract_from_apollo(apollo)
            description = description or d
            tags = tags or t
        if not description:
            description = _ldjson_description(data)
        if description and tags:
            break

    if not tags:
        tags = _genre_links(html_text)
    if not description:
        meta = _META_DESC.search(html_text)
        if meta:
            description = _html.unescape(meta.group(1)).strip()
    return description, tags


# --- parsing helpers ---------------------------------------------------------
def _json_blobs(html_text: str) -> Iterator[str]:
    for match in _SCRIPT.finditer(html_text):
        blob = match.group(1).strip()
        if blob[:1] in "{[":
            yield blob


def _find_apollo(obj: object) -> Optional[dict]:
    """Find the dict that looks like an Apollo cache (has a Book entry)."""
    if isinstance(obj, dict):
        if any(
            isinstance(v, dict) and v.get("__typename") == "Book"
            for v in obj.values()
        ):
            return obj
        for value in obj.values():
            found = _find_apollo(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_apollo(value)
            if found is not None:
                return found
    return None


def _extract_from_apollo(apollo: dict) -> Tuple[str, List[str]]:
    description, tags = "", []
    for value in apollo.values():
        if not (isinstance(value, dict) and value.get("__typename") == "Book"):
            continue
        if not description and value.get("description"):
            description = value["description"]
        book_genres = value.get("bookGenres") or []
        if book_genres and not tags:
            for entry in book_genres:
                genre = entry.get("genre") or {}
                name = genre.get("name")
                if not name:
                    ref = genre.get("__ref")
                    if ref and isinstance(apollo.get(ref), dict):
                        name = apollo[ref].get("name")
                if name:
                    tags.append(name)
        if description and tags:
            break
    return description, tags


def _ldjson_description(data: object) -> str:
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        type_ = item.get("@type", "")
        is_book = type_ == "Book" or (isinstance(type_, list) and "Book" in type_)
        if is_book and item.get("description"):
            return str(item["description"]).strip()
    return ""


def _book_id_from_html(html_text: str) -> str:
    """Pull the numeric Goodreads id from a saved page's canonical URL."""
    canon = re.search(r'<link[^>]*rel="canonical"[^>]*>', html_text)
    if canon:
        match = re.search(r"/book/show/(\d+)", canon.group(0))
        if match:
            return match.group(1)
    og = re.search(r'og:url"[^>]*content="[^"]*?/book/show/(\d+)', html_text)
    if og:
        return og.group(1)
    any_ref = re.search(r"/book/show/(\d+)", html_text)
    return any_ref.group(1) if any_ref else ""


def _genre_links(html_text: str) -> List[str]:
    seen, out = set(), []
    for name in _GENRE_LINK.findall(html_text):
        name = _html.unescape(name).strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _short_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__
