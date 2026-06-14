"""Download cover images so they can be embedded in the Anki deck.

Only books that expose a ``cover_url`` (currently the RSS source) can have a
cover. Each downloaded file is stored in ``media_dir`` and its path recorded
on ``book.cover_filename``; the returned list is ready to hand to
:meth:`AnkiExporter.export` as ``media_files``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Union

import requests

_HEADERS = {"User-Agent": "goodreads-to-anki/1.0 (+https://github.com/SKR-35/Goodreads-to-Anki)"}


def download_covers(
    books: Iterable["object"],
    media_dir: Union[str, Path],
    *,
    timeout: float = 30.0,
    session: Optional[requests.Session] = None,
) -> List[str]:
    """Download cover images and tag each book with its local filename.

    Failures are skipped (a missing cover should never abort an export).
    Returns the list of downloaded file paths.
    """
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    session = session or requests.Session()
    downloaded: List[str] = []

    for book in books:
        url = getattr(book, "cover_url", "")
        if not url:
            continue
        ext = _guess_ext(url)
        key = getattr(book, "book_id", "") or _slug(getattr(book, "title", "book"))
        dest = media_dir / f"gr_cover_{key}{ext}"
        try:
            resp = session.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        except (requests.RequestException, OSError):
            continue
        book.cover_filename = str(dest)
        downloaded.append(str(dest))

    return downloaded


def _guess_ext(url: str) -> str:
    lowered = url.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        if ext in lowered:
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)[:40] or "book"
