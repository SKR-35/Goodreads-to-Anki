"""Enrich books by driving a real Firefox browser (Selenium).

Goodreads sits behind Cloudflare, which blocks plain HTTP libraries like
``requests``. A real browser — optionally using your own Firefox **profile**
so it reuses your cookies and an already-passed Cloudflare challenge — loads
the page like a human would. This mirrors the structure of the DEBE scraper
(Firefox + webdriver-manager + a real User-Agent + WebDriverWait).

Once the page is loaded, the HTML is handed to the same
:func:`goodreads_to_anki.enrich.parse_book_html` used everywhere else, so the
description/tag extraction logic is shared.

Optional extra — install with::

    pip install "goodreads-to-anki[browser]"   # or: pip install selenium webdriver-manager

and have Firefox installed. All Selenium imports are lazy, so the rest of the
package works without these dependencies.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterable, Iterator, List, Optional

from .enrich import (
    _URL,
    EnrichStats,
    ProgressHandler,
    _apply,
    _detail,
    _report,
    _short_error,
    parse_book_html,
)
from .models import Book

# A normal desktop User-Agent (same idea as the DEBE scraper's override).
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/117.0.0.0 Safari/537.36"
)

# When this element is present, the real Goodreads page (not a Cloudflare
# interstitial) has loaded.
_READY_SELECTOR = "script#__NEXT_DATA__"


def _build_driver(headless: bool, profile_path: Optional[str], user_agent: str):
    """Create a Firefox WebDriver, mirroring the DEBE scraper's setup."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    from webdriver_manager.firefox import GeckoDriverManager

    options = Options()
    if profile_path:
        try:
            options.profile = profile_path
        except Exception:  # older/newer Selenium: fall back to the CLI arg
            options.add_argument("-profile")
            options.add_argument(profile_path)
    options.set_preference("general.useragent.override", user_agent)
    if headless:
        options.add_argument("--headless")

    return webdriver.Firefox(
        service=Service(GeckoDriverManager().install()), options=options
    )


@contextmanager
def firefox_driver(
    headless: bool = True,
    profile_path: Optional[str] = None,
    user_agent: str = _DEFAULT_UA,
):
    """Context manager yielding a Firefox driver and quitting it afterwards."""
    driver = _build_driver(headless, profile_path, user_agent)
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def fetch_book_page_browser(driver, book_id: str, *, timeout: float = 30.0, settle: float = 1.5):
    """Navigate to a book page and return ``(description, tags)``.

    Waits for the real page to render, then reuses the shared HTML parser. The
    Selenium wait is best-effort: if it's unavailable or times out, we still
    parse whatever ``page_source`` we have.
    """
    driver.get(_URL.format(book_id=book_id))
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, _READY_SELECTOR))
        )
    except Exception:
        pass
    if settle:
        time.sleep(settle)
    return parse_book_html(driver.page_source)


def enrich_books_browser(
    books: Iterable[Book],
    *,
    headless: bool = True,
    profile_path: Optional[str] = None,
    user_agent: str = _DEFAULT_UA,
    delay: float = 1.0,
    timeout: float = 30.0,
    settle: float = 1.5,
    overwrite_description: bool = False,
    on_progress: Optional[ProgressHandler] = None,
    driver: Optional[object] = None,
) -> EnrichStats:
    """Populate ``description`` and ``tags`` on each book via a real browser.

    Pass ``headless=False`` to watch the window (handy the first time, e.g. to
    solve a Cloudflare/login prompt). Provide ``profile_path`` to reuse an
    existing Firefox profile. ``driver`` may be injected for testing; when
    given it is reused and not closed.
    """
    targets = [b for b in books if b.book_id]
    total = len(targets)
    stats = EnrichStats(total=total)

    if driver is not None:
        _run_loop(driver, targets, total, stats, delay, timeout, settle,
                  overwrite_description, on_progress)
    else:
        with firefox_driver(headless=headless, profile_path=profile_path,
                            user_agent=user_agent) as drv:
            _run_loop(drv, targets, total, stats, delay, timeout, settle,
                      overwrite_description, on_progress)
    return stats


def _run_loop(driver, targets, total, stats, delay, timeout, settle,
              overwrite_description, on_progress) -> None:
    for index, book in enumerate(targets, start=1):
        if index > 1 and delay:
            time.sleep(delay)
        try:
            description, tags = fetch_book_page_browser(
                driver, book.book_id, timeout=timeout, settle=settle
            )
        except Exception as exc:
            stats.failed += 1
            if not stats.first_error:
                stats.first_error = _short_error(exc)
            _report(on_progress, index, total, book, "error", _short_error(exc))
            continue
        if _apply(book, description, tags, overwrite_description):
            stats.enriched += 1
            _report(on_progress, index, total, book, "ok", _detail(tags))
        else:
            _report(on_progress, index, total, book, "no_data", "")
