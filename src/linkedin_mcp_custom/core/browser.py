"""Browser management — Patchright singleton wrapper with page pool."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from patchright.async_api import BrowserContext, Playwright

if TYPE_CHECKING:
    from patchright.async_api import Page

logger = logging.getLogger(__name__)

# Resource types to block during headless scraping (speed + bandwidth)
_BLOCKED_RESOURCE_TYPES = {"image", "font", "media"}

# Tracking/analytics domains to block
_BLOCKED_DOMAINS = re.compile(
    r"(google-analytics|googletagmanager|doubleclick|facebook|fbcdn|"
    r"linkedin\.com\/analytics|bat\.bing|scorecardresearch|hotjar|"
    r"clarity\.ms|amplitude|mixpanel|optimizely|fullstory)",
    re.IGNORECASE,
)

# Singleton state
_playwright: Playwright | None = None
_context: BrowserContext | None = None
_page: Page | None = None
_browser_lock: asyncio.Lock = asyncio.Lock()  # guard for concurrent get_or_create_browser

# Page pool for concurrent scraping
_page_pool: list[Page] = []
MAX_PAGE_POOL_SIZE = 3  # matches default MAX_CONCURRENT

# Track in-flight navigations for clean shutdown
_PENDING_NAV_TASKS: set[asyncio.Task] = set()

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

    # Fast path without lock — already initialized
    if _context is not None:
        pages = _context.pages
        if pages and not pages[0].is_closed():
            return _context

    async with _browser_lock:
        # Double-check after acquiring lock (another task may have initialized)
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

    # Block unnecessary resources for speed (images, fonts, media, tracking)
    await _context.route(
        re.compile(r".*"),
        lambda route: (
            route.abort()
            if route.request.resource_type in _BLOCKED_RESOURCE_TYPES
            or _BLOCKED_DOMAINS.search(route.request.url)
            else route.continue_()
        ),
    )
    logger.info(
        "Resource blocking active: types=%s, tracking domains blocked",
        _BLOCKED_RESOURCE_TYPES,
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


async def create_page() -> Page:
    """Get a page from the pool (round-robin, up to MAX_PAGE_POOL_SIZE).

    Creates new pages until the pool reaches MAX_PAGE_POOL_SIZE (5),
    then cycles through existing pages in round-robin order.

    Use for parallel/concurrent scraping where multiple pages
    need independent navigation without race conditions.
    """
    global _page_pool

    # Clean up any closed pages
    _page_pool = [p for p in _page_pool if not p.is_closed()]

    ctx = await get_browser_context()

    # Fill pool up to max before cycling
    if len(_page_pool) < MAX_PAGE_POOL_SIZE:
        page = await ctx.new_page()
        _page_pool.append(page)
        return page

    # Pool full, round-robin
    page = _page_pool.pop(0)
    _page_pool.append(page)
    return page


def _track_nav_task(task: asyncio.Task | None) -> None:
    """Register an in-flight navigation task for clean shutdown tracking."""
    if task is None:
        return
    _PENDING_NAV_TASKS.add(task)
    task.add_done_callback(_PENDING_NAV_TASKS.discard)


async def _drain_pending_navs(timeout: float = 3.0) -> None:
    """Wait briefly for in-flight navigations to settle before closing."""
    if not _PENDING_NAV_TASKS:
        return
    _, pending = await asyncio.wait(
        _PENDING_NAV_TASKS, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()
    _PENDING_NAV_TASKS.clear()


async def close_browser() -> None:
    """Close the browser and cleanup resources."""
    global _context, _page, _playwright, _page_pool

    # Let in-flight navigations settle before closing pages
    await _drain_pending_navs()

    for p in _page_pool:
        try:
            await p.close()
        except Exception:
            pass
    _page_pool = []

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
