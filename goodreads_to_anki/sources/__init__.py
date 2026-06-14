"""Book sources: pluggable readers that yield :class:`~goodreads_to_anki.models.Book`.

``CsvSource`` is stdlib-only. ``RssSource`` needs ``requests`` and is imported
lazily so that CSV-only workflows don't require it.
"""

from .base import BookSource
from .csv_source import CsvSource

__all__ = ["BookSource", "CsvSource", "RssSource"]


def __getattr__(name: str):  # PEP 562 lazy import
    if name == "RssSource":
        from .rss_source import RssSource

        return RssSource
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
