"""Configuration object that bundles the options for one export run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExportConfig:
    """All the knobs for a single Goodreads -> Anki export."""

    source: str = "csv"  # "csv" or "rss"
    # CSV source
    input_path: Optional[Path] = None
    # RSS source
    user_id: Optional[str] = None
    shelf: str = "read"
    per_page: int = 100
    # Filtering
    only_read: bool = False
    only_rated: bool = False
    limit: Optional[int] = None
    # Enrichment (scrape description + tags from each book's Goodreads page)
    enrich: bool = False
    enrich_delay: float = 1.0
    enrich_html: Optional[Path] = None  # use saved HTML pages instead of fetching
    enrich_browser: bool = False        # use a real Firefox browser (Selenium)
    headless: bool = True               # run that browser headless
    firefox_profile: Optional[str] = None
    # Output
    output_path: Path = Path("goodreads.apkg")
    deck_name: Optional[str] = None
    download_covers: bool = False

    def resolved_deck_name(self) -> str:
        if self.deck_name:
            return self.deck_name
        return f"Goodreads::{self.shelf}"
