"""goodreads-to-anki: turn your Goodreads library into an Anki deck.

The top-level package is deliberately light: it does NOT import the Anki
exporter or the RSS source at import time, so that simply importing
``goodreads_to_anki`` (or the CSV source) does not require the optional
third-party dependencies (genanki, requests). Import those submodules
directly where you need them.
"""

from .models import Book

__all__ = ["Book", "__version__"]
__version__ = "0.1.0"
