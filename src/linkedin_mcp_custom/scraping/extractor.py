"""LinkedInExtractor — navigate, scroll, extract innerText, strip noise."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from patchright.async_api import Page

from linkedin_mcp_custom.core.auth import ensure_authenticated
from linkedin_mcp_custom.core.exceptions import (
    AuthenticationError,
    LinkedInScraperException,
    RateLimitError,
)
from linkedin_mcp_custom.scraping.utils import (
    JOBS_TRACKER_URL,
    JOB_VIEW_URL,
    RATE_LIMITED_MSG,
    is_rate_limited,
    strip_noise,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedSection:
    """Result of extracting a single page section."""

    text: str | None = None
    error: str | None = None
    references: dict[str, Any] = field(default_factory=dict)


class LinkedInExtractor:
    """Core scraping engine for LinkedIn pages.

    Uses innerText extraction for resilient data capture.
    One section = one navigation (per stickerdaniel pattern).
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    @property
    def page(self) -> Page:
        return self._page

    # ── Core extraction methods ──────────────────────────────────────

    async def navigate_to_page(
        self,
        url: str,
        timeout: float = 30000,
    ) -> None:
        """Navigate to a URL and wait for the page to load.

        Raises:
            AuthenticationError: If not logged in.
            RateLimitError: If LinkedIn rate-limited the request.
        """
        logger.info("Navigating to %s", url)

        try:
            resp = await self._page.goto(
                url, wait_until="domcontentloaded", timeout=timeout
            )
        except Exception as e:
            raise LinkedInScraperException(f"Navigation failed: {e}") from e

        # Check HTTP status
        if resp and resp.status >= 400:
            text = await self._page.text_content("body") or ""
            if is_rate_limited(text):
                raise RateLimitError("LinkedIn rate-limited this request")
            raise LinkedInScraperException(f"HTTP {resp.status} for {url}")

        # Wait for main content
        await self._page.wait_for_timeout(2000)

    async def extract_page(
        self,
        url: str,
        section_name: str = "content",
        scroll: bool = False,
        timeout: float = 30000,
    ) -> ExtractedSection:
        """Navigate to a URL and extract clean innerText.

        Args:
            url: Full LinkedIn URL to navigate to.
            section_name: Label for this section (used in result dict).
            scroll: Whether to scroll to bottom before extraction.
            timeout: Navigation timeout in ms.

        Returns:
            ExtractedSection with clean text or error.
        """
        try:
            await self.navigate_to_page(url, timeout=timeout)
            await ensure_authenticated(self._page)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            return ExtractedSection(error=str(e))

        # Scroll if requested (loads lazy content)
        if scroll:
            await self._scroll_to_bottom()

        # Extract innerText from <main> (preferred) or <body>
        text = await self._extract_inner_text()

        if not text or not text.strip():
            return ExtractedSection(error="No content found on page")

        if is_rate_limited(text):
            return ExtractedSection(text=RATE_LIMITED_MSG)

        cleaned = strip_noise(text)
        return ExtractedSection(text=cleaned)

    # ── Specific scraping methods ────────────────────────────────────

    async def scrape_job(self, job_id: str) -> dict[str, Any]:
        """Scrape full job posting details with structured fields.

        Args:
            job_id: LinkedIn numeric job ID (e.g. "4252026496").

        Returns:
            Dict with url, sections, job_title, company, location.
            The 'job_posting' section contains the full raw text.
        """
        url = f"{JOB_VIEW_URL}{job_id}/"

        extracted = await self.extract_page(
            url, section_name="job_posting", scroll=True
        )

        sections: dict[str, str] = {}
        section_errors: dict[str, str] = {}

        if extracted.text and extracted.text != RATE_LIMITED_MSG:
            sections["job_posting"] = extracted.text
        elif extracted.error:
            section_errors["job_posting"] = extracted.error
        elif extracted.text == RATE_LIMITED_MSG:
            section_errors["job_posting"] = "Rate limited"

        # Extract structured fields from page DOM
        metadata = await self._extract_job_metadata()

        result: dict[str, Any] = {
            "url": url,
            "job_title": metadata.get("title", ""),
            "company": metadata.get("company", ""),
            "location": metadata.get("location", ""),
        }

        if sections:
            result["sections"] = sections
        if section_errors:
            result["section_errors"] = section_errors

        return result

    async def scrape_saved_jobs(self) -> dict[str, Any]:
        """Scrape the LinkedIn saved jobs tracker page.

        Returns:
            Dict with url, sections (raw text), and job_ids list.
        """
        extracted = await self.extract_page(
            JOBS_TRACKER_URL, section_name="saved_jobs", scroll=True
        )

        sections: dict[str, str] = {}
        section_errors: dict[str, str] = {}

        if extracted.text and extracted.text != RATE_LIMITED_MSG:
            sections["saved_jobs"] = extracted.text
        elif extracted.error:
            section_errors["saved_jobs"] = extracted.error

        # Extract individual job IDs from the page
        job_ids = await self._extract_job_ids()

        result: dict[str, Any] = {"url": JOBS_TRACKER_URL}

        if sections:
            result["sections"] = sections
        if job_ids:
            result["job_ids"] = job_ids
        if section_errors:
            result["section_errors"] = section_errors

        return result

    # ── Internal helpers ─────────────────────────────────────────────

    async def _extract_inner_text(self) -> str | None:
        """Extract innerText from <main> or <body> as fallback."""
        try:
            text = await self._page.evaluate("""
                () => {
                    const main = document.querySelector('main');
                    if (main && main.innerText.trim()) {
                        return main.innerText;
                    }
                    return document.body?.innerText || '';
                }
            """)
            return str(text) if text else None
        except Exception as e:
            logger.warning("innerText extraction failed: %s", e)
            return None

    async def _extract_job_ids(self) -> list[str]:
        """Extract all unique LinkedIn job IDs from the current page."""
        try:
            ids = await self._page.evaluate("""
                () => {
                    const links = document.querySelectorAll(
                        'a[href*="/jobs/view/"]'
                    );
                    const seen = new Set();
                    const result = [];
                    for (const a of links) {
                        const match = a.href.match(/\\/jobs\\/view\\/(\\d+)/);
                        if (match && !seen.has(match[1])) {
                            seen.add(match[1]);
                            result.push(match[1]);
                        }
                    }
                    return result;
                }
            """)
            return list(ids) if isinstance(ids, list) else []
        except Exception as e:
            logger.warning("Job ID extraction failed: %s", e)
            return []

    async def _extract_job_metadata(self) -> dict[str, str]:
        """Extract job title, company, and location from job page DOM."""
        try:
            data = await self._page.evaluate("""
                () => {
                    const result = {title: '', company: '', location: ''};
                    const titleEl = document.querySelector(
                        '.job-details-jobs-unified-top-card__job-title h1, ' +
                        '.jobs-unified-top-card__job-title h1, ' +
                        '.job-view-layout h1, ' +
                        'h1'
                    );
                    if (titleEl) result.title = titleEl.innerText.trim();
                    const companyEl = document.querySelector(
                        '.job-details-jobs-unified-top-card__company-name a, ' +
                        '.jobs-unified-top-card__company-name a, ' +
                        '.jobs-details__main-content .job-view-layout a'
                    );
                    if (companyEl) result.company = companyEl.innerText.trim();
                    const locEl = document.querySelector(
                        '.job-details-jobs-unified-top-card__bullet, ' +
                        '.jobs-unified-top-card__bullet, ' +
                        '[class*="top-card"] [class*="bullet"]'
                    );
                    if (locEl) result.location = locEl.innerText.trim();
                    return result;
                }
            """)
            return {
                "title": str(data.get("title", "")),
                "company": str(data.get("company", "")),
                "location": str(data.get("location", "")),
            }
        except Exception as e:
            logger.warning("Job metadata extraction failed: %s", e)
            return {"title": "", "company": "", "location": ""}

    async def _scroll_to_bottom(self) -> None:
        """Scroll page to bottom to trigger lazy loading."""
        try:
            await self._page.evaluate("""
                () => {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            """)
            await self._page.wait_for_timeout(1500)
        except Exception as e:
            logger.warning("Scroll failed: %s", e)
