"""LinkedIn authentication — cookie-based session management."""

from __future__ import annotations

import logging
import time

from patchright.async_api import Page

from linkedin_mcp_custom.core.exceptions import AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)


async def wait_for_manual_login(page: Page, timeout: int = 300) -> bool:
    """Wait for user to manually log in to LinkedIn via the browser.

    Opens LinkedIn, lets the user type credentials, and waits until
    the page navigates to the feed (signal of successful login).

    Args:
        page: Patchright page instance.
        timeout: Max seconds to wait for login (default 5 min).

    Returns:
        True if login was detected within timeout.

    Raises:
        AuthenticationError: If login not detected within timeout.
    """
    await page.goto("https://www.linkedin.com/", wait_until="domcontentloaded")

    logger.info("Waiting for manual LinkedIn login...")
    start = time.time()

    while time.time() - start < timeout:
        current_url = page.url

        if "/feed/" in current_url:
            logger.info("Login detected — on LinkedIn feed")
            return True

        if "/checkpoint/" in current_url:
            logger.warning("Checkpoint/challenge page detected")
            raise AuthenticationError(
                "LinkedIn challenge page. Complete verification in browser."
            )

        await page.wait_for_timeout(1000)

    raise AuthenticationError(
        f"Manual login not completed within {timeout}s. Run with --login to try again."
    )


async def is_logged_in(page: Page) -> bool:
    """Check if the current session is authenticated on LinkedIn.

    Navigates to linkedin.com and checks if we land on the feed.
    """
    try:
        await page.goto(
            "https://www.linkedin.com/feed/",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        current_url = page.url

        if "/feed/" in current_url:
            return True

        if "/login" in current_url or "/checkpoint" in current_url:
            return False

        # Check for login redirect
        body = await page.text_content("body")
        if body and "Sign in" in body and "Email" in body:
            return False

        return False
    except Exception as e:
        logger.warning("Login check failed: %s", e)
        return False


async def detect_rate_limit(page: Page) -> bool:
    """Check if LinkedIn rate-limited us."""
    body_text = await page.text_content("body") or ""

    rate_limit_signals = [
        "too many requests",
        "rate limited",
        "please try again later",
        "unusual traffic",
    ]

    return any(signal in body_text.lower() for signal in rate_limit_signals)


async def ensure_authenticated(page: Page) -> None:
    """Ensure we have a valid LinkedIn session.

    Raises:
        AuthenticationError: If not logged in.
        RateLimitError: If rate-limited.
    """
    if await detect_rate_limit(page):
        raise RateLimitError("LinkedIn rate-limited this request. Wait and retry.")

    if not await is_logged_in(page):
        raise AuthenticationError("Not authenticated. Run: linkedin-mcp --login")
