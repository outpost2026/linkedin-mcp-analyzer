"""Browser management — Patchright singleton wrapper."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from patchright.async_api import BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

# Singleton state
_playwright: Playwright | None = None
_context: BrowserContext | None = None
_page: Page | None = None
_browser_lock: asyncio.Lock = asyncio.Lock()

# Profile directory for persistent cookies
PROFILE_DIR = Path.home() / ".linkedin-mcp-custom" / "profile"


def _ensure_profile_dir() -> Path:
    """Create and return the persistent profile directory."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILE_DIR


async def get_or_create_browser(headless: bool = False) -> BrowserContext:
    """Get or create the singleton Patchright browser context.

    Uses persistent context (user data dir) so cookies survive restarts.

    Args:
        headless: Whether to run in headless mode. Default False so
                  the user can see the login dialog on first use.

    Returns:
        Patchright BrowserContext instance (persistent).
    """
    global _context, _page, _playwright

    # Fast path without lock
    if _context is not None:
        pages = _context.pages
        if pages and not pages[0].is_closed():
            return _context

    async with _browser_lock:
        # Double-check after acquiring lock
        if _context is not None:
            pages = _context.pages
            if pages and not pages[0].is_closed():
                return _context

        from patchright.async_api import async_playwright

        profile_dir = _ensure_profile_dir()
        logger.info("Launching Patchright browser (profile: %s)", profile_dir)

        _playwright = await async_playwright().start()
        _context = await _playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            no_viewport=True,
        )

        pages = _context.pages
        _page = pages[0] if pages else await _context.new_page()

        return _context


async def get_page() -> Page:
    """Get the singleton page instance (creates browser if needed)."""
    global _page

    if _page is not None and not _page.is_closed():
        return _page

    await get_or_create_browser()
    assert _page is not None
    return _page


async def get_browser_context() -> BrowserContext:
    """Get the singleton browser context."""
    global _context
    if _context is not None:
        return _context
    return await get_or_create_browser()


async def close_browser() -> None:
    """Close the browser and cleanup resources."""
    global _context, _page, _playwright

    if _page is not None and not _page.is_closed():
        await _page.close()
    _page = None

    if _context is not None:
        await _context.close()
    _context = None

    if _playwright is not None:
        await _playwright.stop()
    _playwright = None

    logger.info("Browser closed")


async def close_session() -> None:
    """Alias for close_browser — for MCP session cleanup."""
    await close_browser()
