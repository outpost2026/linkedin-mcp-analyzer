"""Custom exceptions for LinkedIn scraping."""


class LinkedInScraperException(Exception):
    """Base exception for all LinkedIn scraper errors."""


class AuthenticationError(LinkedInScraperException):
    """Session is invalid or expired. User needs to re-login."""


class RateLimitError(LinkedInScraperException):
    """LinkedIn rate-limited the request. Wait and retry."""


class ElementNotFoundError(LinkedInScraperException):
    """Expected element not found on the page."""


class BrowserError(LinkedInScraperException):
    """Browser or Playwright-level error."""
