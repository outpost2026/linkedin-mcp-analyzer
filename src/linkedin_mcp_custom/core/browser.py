"""Browser management — Patchright singleton wrapper.

P2: Fingerprint mix — random viewport, user-agent pool, timezone, locale.
Each launch randomizes fingerprint parameters to reduce correlation.
"""

from __future__ import annotations

import asyncio
import logging
import random
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

# P2: Viewport pool — realistic desktop resolutions (hardcoded fallback)
_VIEWPORT_POOL = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 800},
]

# P2: User-agent pool — European CZ/EN variants (hardcoded fallback)
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]


def _fingerprint_from_config() -> tuple[dict, str, str, str] | None:
    """Read fingerprint pools from active AppConfig runtime.

    Returns (viewport, ua, locale, timezone) or None if config not set.
    """
    try:
        from linkedin_mcp_custom.config import get_active_config

        cfg = get_active_config()
        if cfg is None or not cfg.runtime.fingerprint_mix:
            return None
        rt = cfg.runtime
        return (
            rt.random_viewport(),
            rt.random_ua(),
            rt.random_locale(),
            rt.random_timezone(),
        )
    except Exception:
        return None


def _ensure_profile_dir() -> Path:
    """Create and return the persistent profile directory."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILE_DIR


async def get_or_create_browser(headless: bool = False) -> BrowserContext:
    """Get or create the singleton Patchright browser context.

    P2: Each launch picks a random profile directory and random
    viewport/user-agent to reduce LinkedIn fingerprint correlation.

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

        # P2: Fingerprint from config (if set) or hardcoded fallback
        fp = _fingerprint_from_config()
        if fp:
            viewport, ua, locale, timezone_id = fp
        else:
            viewport = random.choice(_VIEWPORT_POOL)
            ua = random.choice(_UA_POOL)
            locale = random.choice(["cs-CZ", "en-US", "en-GB"])
            timezone_id = random.choice(["Europe/Prague", "Europe/Berlin", "Europe/London"])

        logger.info(
            "Launching browser (profile: %s, viewport: %dx%d, locale: %s)",
            profile_dir.name,
            viewport["width"],
            viewport["height"],
            locale,
        )

        _playwright = await async_playwright().start()
        _context = await _playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            no_viewport=True,
            locale=locale,
            timezone_id=timezone_id,
        )

        pages = _context.pages
        _page = pages[0] if pages else await _context.new_page()
        await _page.set_viewport_size(viewport)

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
