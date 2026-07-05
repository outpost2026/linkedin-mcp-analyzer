"""Browser management — Patchright singleton wrapper."""

from __future__ import annotations

import logging
from pathlib import Path

from patchright.async_api import Browser, BrowserContext, Page, Playwright

from linkedin_mcp_custom.core.exceptions import BrowserError

logger = logging.getLogger(__name__)

# Singleton state
_playwright: Playwright | None = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_page: Page | None = None

# Profile directory for persistent cookies
PROFILE_DIR = Path.home() / ".linkedin-mcp-custom" / "profile"


def _ensure_profile_dir() -> Path:
    """Create and return the persistent profile directory."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILE_DIR


async def get_or_create_browser(headless: bool = False) -> Browser:
    """Get or create the singleton Patchright browser instance.

    Args:
        headless: Whether to run in headless mode. Default False so
                  the user can see the login dialog on first use.

    Returns:
        Patchright Browser instance.
    """
    global _browser, _playwright

    if _browser is not None and _browser.is_connected():
        return _browser

    from patchright.async_api import async_playwright

    profile_dir = _ensure_profile_dir()
    logger.info("Launching Patchright browser (profile: %s)", profile_dir)

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
        no_viewport=True,
    )

    _context = _browser if isinstance(_browser, BrowserContext) else None
    pages = _context.pages if _context else []
    _page = pages[0] if pages else await _context.new_page()

    return _browser


async def get_page() -> Page:
    """Get the singleton page instance (creates browser if needed)."""
    global _page, _browser

    if _page is not None and not _page.is_closed():
        return _page

    await get_or_create_browser()

    if _context is None:
        raise BrowserError("Browser context not initialized")

    pages = _context.pages
    _page = pages[0] if pages else await _context.new_page()
    return _page


async def get_browser_context() -> BrowserContext:
    """Get the singleton browser context."""
    global _context
    if _context is not None:
        return _context
    await get_or_create_browser()
    return _context


async def close_browser() -> None:
    """Close the browser and cleanup resources."""
    global _browser, _context, _page, _playwright

    if _page is not None and not _page.is_closed():
        await _page.close()
    _page = None

    if _context is not None:
        await _context.close()
    _context = None

    if _browser is not None:
        await _browser.close()
    _browser = None

    if _playwright is not None:
        await _playwright.stop()
    _playwright = None

    logger.info("Browser closed")


async def close_session() -> None:
    """Alias for close_browser — for MCP session cleanup."""
    await close_browser()
