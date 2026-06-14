"""Small, dependency-free parsing helpers shared by the data sources.

Goodreads exports are messy in predictable ways (Excel-escaped ISBNs,
``YYYY/MM/DD`` dates, ``0`` meaning "unrated", comma-joined shelves).
Keeping the quirks isolated here keeps the source modules readable.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional

# Goodreads wraps ISBNs as an Excel formula, e.g. ="9780743273565"
_EXCEL_FORMULA = re.compile(r'^="?(.*?)"?$')


def clean_isbn(value: Optional[str]) -> str:
    """Strip the ``="..."`` Excel wrapper Goodreads puts around ISBNs."""
    if not value:
        return ""
    value = value.strip()
    match = _EXCEL_FORMULA.match(value)
    if match:
        value = match.group(1)
    return value.strip().strip('"')


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_date(value: Optional[str], *, fmts: Optional[List[str]] = None) -> Optional[date]:
    """Parse the handful of date formats Goodreads emits.

    CSV export uses ``YYYY/MM/DD``; the RSS feed uses RFC-822-ish strings.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    fmts = fmts or [
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %z",  # RSS pubDate
        "%a, %d %b %Y %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def split_shelves(value: Optional[str]) -> List[str]:
    """Split a Goodreads ``Bookshelves`` string into a clean list."""
    if not value:
        return []
    parts = re.split(r"[;,]", value)
    return [p.strip() for p in parts if p.strip()]


def stars(rating: int) -> str:
    """Render a 0-5 integer rating as filled/empty stars."""
    rating = max(0, min(5, int(rating or 0)))
    if rating == 0:
        return "Not rated"
    return "★" * rating + "☆" * (5 - rating)
