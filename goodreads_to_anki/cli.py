"""Command-line interface for goodreads-to-anki.

Examples
--------
From a Goodreads CSV export::

    goodreads-to-anki csv --input goodreads_library_export.csv \\
        --only-read --output read.apkg

From any public profile's RSS feed (with cover images)::

    goodreads-to-anki rss --user-id 12345678 --shelf read --covers \\
        --output friend.apkg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .config import ExportConfig
from .pipeline import run


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "t", "yes", "y", "on")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goodreads-to-anki",
        description="Turn your Goodreads library into an Anki deck.",
    )
    sub = parser.add_subparsers(dest="source", required=True)

    # Shared options applied to both subcommands.
    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("-o", "--output", type=Path, default=Path("goodreads.apkg"),
                       help="output .apkg path (default: goodreads.apkg)")
        p.add_argument("--deck-name", default=None, help="Anki deck name")
        p.add_argument("--only-read", action="store_true",
                       help="only books on the 'read' shelf")
        p.add_argument("--only-rated", action="store_true",
                       help="only books you gave a star rating")
        p.add_argument("--limit", type=int, default=None,
                       help="stop after N books (useful for testing)")
        p.add_argument("--enrich", action="store_true",
                       help="fetch description + genre tags from each book's "
                            "Goodreads page (network; best-effort)")
        p.add_argument("--enrich-html", type=Path, default=None, metavar="PATH",
                       help="enrich from saved Goodreads HTML page(s) instead "
                            "of fetching: a file or a folder of .htm/.html")
        p.add_argument("--enrich-browser", action="store_true",
                       help="enrich via a real Firefox browser (Selenium) to "
                            "get past Cloudflare; needs the 'browser' extra")
        p.add_argument("--headless", type=_parse_bool, default=True,
                       metavar="true|false",
                       help="run the browser headless (default: true); "
                            "use 'false' to watch the window")
        p.add_argument("--firefox-profile", default=None, metavar="PATH",
                       help="Firefox profile dir to reuse (your cookies / an "
                            "already-passed Cloudflare challenge)")
        p.add_argument("--enrich-delay", type=float, default=1.0,
                       help="seconds between enrichment requests (default: 1.0)")

    p_csv = sub.add_parser("csv", help="read a Goodreads CSV library export")
    p_csv.add_argument("-i", "--input", type=Path, required=True,
                       help="path to goodreads_library_export.csv")
    add_common(p_csv)

    p_rss = sub.add_parser("rss", help="read a public Goodreads shelf RSS feed")
    p_rss.add_argument("-u", "--user-id", required=True,
                       help="numeric Goodreads user id")
    p_rss.add_argument("--shelf", default="read", help="shelf name (default: read)")
    p_rss.add_argument("--per-page", type=int, default=100, help="feed page size")
    p_rss.add_argument("--covers", action="store_true",
                       help="download cover images and embed them")
    add_common(p_rss)

    return parser


def args_to_config(args: argparse.Namespace) -> ExportConfig:
    return ExportConfig(
        source=args.source,
        input_path=getattr(args, "input", None),
        user_id=getattr(args, "user_id", None),
        shelf=getattr(args, "shelf", "read"),
        per_page=getattr(args, "per_page", 100),
        only_read=args.only_read,
        only_rated=args.only_rated,
        limit=args.limit,
        enrich=args.enrich,
        enrich_delay=args.enrich_delay,
        enrich_html=args.enrich_html,
        enrich_browser=args.enrich_browser,
        headless=args.headless,
        firefox_profile=args.firefox_profile,
        output_path=args.output,
        deck_name=args.deck_name,
        download_covers=getattr(args, "covers", False),
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    config = args_to_config(args)
    try:
        path = run(config)
    except Exception as exc:  # surface a clean message, not a traceback
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
