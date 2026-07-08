"""LinkedIn authentication — cookie-based session management."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from patchright.async_api import Page

from linkedin_mcp_custom.core.exceptions import AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)

# Session state tracking for proactive expiry detection
_last_auth_check: float | None = None
_last_auth_ok: bool | None = None
SESSION_CHECK_INTERVAL = 60  # seconds between proactive checks
SESSION_WARN_THRESHOLD = 86400  # warn if session older than 24h

CHECKPOINT_PATTERNS = [
    "/checkpoint/",
    "/challenge/",
    "help us confirm it's you",
    "security verification",
    "enter your verification code",
]


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
            _mark_auth_ok()
            return True

        if _is_checkpoint_page(current_url):
            logger.warning(
                "Checkpoint/challenge page detected — waiting for user to complete verification"
            )

        await page.wait_for_timeout(1000)

    raise AuthenticationError(
        f"Manual login not completed within {timeout}s. Run with --login to try again."
    )


def _is_checkpoint_page(url: str) -> bool:
    """Detect LinkedIn checkpoint/challenge/verification pages."""
    return any(p in url.lower() for p in CHECKPOINT_PATTERNS)


def _mark_auth_ok() -> None:
    global _last_auth_check, _last_auth_ok
    _last_auth_check = time.time()
    _last_auth_ok = True


def _mark_auth_expired() -> None:
    global _last_auth_check, _last_auth_ok
    _last_auth_check = time.time()
    _last_auth_ok = False


async def is_logged_in(page: Page) -> bool:
    """Check if the current session is authenticated on LinkedIn.

    Navigates to linkedin.com and checks if we land on the feed.
    Also detects checkpoint/challenge pages for detailed diagnostics.
    """
    try:
        await page.goto(
            "https://www.linkedin.com/feed/",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        current_url = page.url

        if "/feed/" in current_url:
            _mark_auth_ok()
            return True

        if _is_checkpoint_page(current_url):
            logger.warning("Checkpoint/challenge page detected at: %s", current_url)
            _mark_auth_expired()
            return False

        if "/login" in current_url:
            _mark_auth_expired()
            return False

        body = await page.text_content("body")
        body_text = (body or "").lower()
        if "sign in" in body_text and "email" in body_text:
            _mark_auth_expired()
            return False

        if _is_checkpoint_page(body_text):
            logger.warning("Checkpoint/challenge detected in page body")
            _mark_auth_expired()
            return False

        _mark_auth_expired()
        return False
    except Exception as e:
        logger.warning("Login check failed: %s", e)
        _mark_auth_expired()
        return False


def get_session_age() -> float | None:
    """Return session age in hours, or None if never authenticated."""
    if _last_auth_check is None or not _last_auth_ok:
        return None
    return round((time.time() - _last_auth_check) / 3600, 1)


def session_needs_refresh() -> bool:
    """Return True if session is older than SESSION_WARN_THRESHOLD."""
    age = get_session_age()
    if age is None:
        return True
    return age * 3600 > SESSION_WARN_THRESHOLD


async def check_session_status(page: Page) -> dict:
    """Detailed session status check with diagnostics.

    Returns a dict with:
      - status: "ok" | "expired" | "checkpoint" | "error"
      - detail: human-readable message
      - last_valid: ISO timestamp of last known good auth (or None)
      - session_age_hours: hours since last valid auth (or None)
      - url: current page URL after check
    """
    last_valid_str = None
    session_age = get_session_age()
    if _last_auth_check is not None and _last_auth_ok:
        last_valid_str = datetime.fromtimestamp(_last_auth_check, tz=UTC).isoformat()

    try:
        await page.goto(
            "https://www.linkedin.com/feed/",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        current_url = page.url

        if "/feed/" in current_url:
            _mark_auth_ok()
            result: dict = {
                "status": "ok",
                "detail": "Session valid — authenticated on LinkedIn feed",
                "last_valid": datetime.now(UTC).isoformat(),
                "session_age_hours": get_session_age(),
                "url": current_url,
            }
            if session_age is not None and session_age > 24:
                result["warning"] = f"Session older than 24h ({session_age}h), consider re-login"
            if session_needs_refresh():
                result["warning"] = (
                    f"Session age {session_age}h exceeds 24h threshold, re-login recommended"
                )
            return result

        if _is_checkpoint_page(current_url):
            _mark_auth_expired()
            body = (await page.text_content("body") or "")[:500]
            return {
                "status": "checkpoint",
                "detail": f"LinkedIn checkpoint/challenge page: {current_url}",
                "last_valid": last_valid_str,
                "session_age_hours": session_age,
                "url": current_url,
                "body_preview": body,
            }

        if "/login" in current_url:
            _mark_auth_expired()
            return {
                "status": "expired",
                "detail": "Session expired — redirected to login page",
                "last_valid": last_valid_str,
                "session_age_hours": session_age,
                "url": current_url,
            }

        return {
            "status": "unknown",
            "detail": f"Unexpected URL after auth check: {current_url}",
            "last_valid": last_valid_str,
            "session_age_hours": session_age,
            "url": current_url,
        }
    except Exception as e:
        _mark_auth_expired()
        return {
            "status": "error",
            "detail": f"Auth check failed: {e}",
            "last_valid": last_valid_str,
            "session_age_hours": session_age,
            "url": "",
        }


async def ensure_authenticated(page: Page, force_check: bool = False) -> None:
    """Ensure we have a valid LinkedIn session.

    Uses cached auth state to avoid unnecessary navigation (unless force_check).
    Detects checkpoint/challenge pages and raises descriptive errors.

    Raises:
        AuthenticationError: If not logged in or on checkpoint page.
        RateLimitError: If rate-limited.
    """
    global _last_auth_check

    now = time.time()
    if (
        not force_check
        and _last_auth_check is not None
        and _last_auth_ok
        and (now - _last_auth_check) < SESSION_CHECK_INTERVAL
    ):
        return

    if await detect_rate_limit(page):
        raise RateLimitError("LinkedIn rate-limited this request. Wait and retry.")

    current_url = page.url
    if _is_checkpoint_page(current_url):
        raise AuthenticationError(
            f"LinkedIn checkpoint/challenge detected at: {current_url}. "
            "Run 'linkedin-mcp --login' to re-authenticate manually."
        )

    if not await is_logged_in(page):
        if _is_checkpoint_page(page.url):
            raise AuthenticationError(
                f"LinkedIn checkpoint/challenge page active: {page.url}. "
                "Complete verification via: linkedin-mcp --login"
            )
        raise AuthenticationError("Not authenticated. Run: linkedin-mcp --login")


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
