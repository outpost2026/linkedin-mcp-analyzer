"""Core browser management and authentication."""

from linkedin_mcp_custom.core.auth import (
    detect_rate_limit,
    ensure_authenticated,
    is_logged_in,
    wait_for_manual_login,
)
from linkedin_mcp_custom.core.browser import (
    close_browser,
    close_session,
    get_browser_context,
    get_or_create_browser,
    get_page,
)
from linkedin_mcp_custom.core.exceptions import (
    AuthenticationError,
    BrowserError,
    ElementNotFoundError,
    LinkedInScraperException,
    RateLimitError,
)

__all__ = [
    "AuthenticationError",
    "BrowserError",
    "ElementNotFoundError",
    "LinkedInScraperException",
    "RateLimitError",
    "close_browser",
    "close_session",
    "detect_rate_limit",
    "ensure_authenticated",
    "get_browser_context",
    "get_or_create_browser",
    "get_page",
    "is_logged_in",
    "wait_for_manual_login",
]
