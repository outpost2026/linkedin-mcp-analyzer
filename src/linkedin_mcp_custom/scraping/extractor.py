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
    JOB_VIEW_URL,
    JOBS_TRACKER_URL,
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
            resp = await self._page.goto(url, wait_until="domcontentloaded", timeout=timeout)
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

        Note: authentication check happens before navigation so
        is_logged_in() doesn't navigate away from the target page.

        Args:
            url: Full LinkedIn URL to navigate to.
            section_name: Label for this section (used in result dict).
            scroll: Whether to scroll to bottom before extraction.
            timeout: Navigation timeout in ms.

        Returns:
            ExtractedSection with clean text or error.
        """
        try:
            await ensure_authenticated(self._page)
            await self.navigate_to_page(url, timeout=timeout)
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

        extracted = await self.extract_page(url, section_name="job_posting", scroll=True)

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
        """Scrape the LinkedIn saved jobs tracker page with pagination.

        Returns:
            Dict with url, sections (raw text), and job_ids list.
        """
        all_job_ids: list[str] = []
        all_text: list[str] = []

        # First page
        extracted = await self.extract_page(
            JOBS_TRACKER_URL, section_name="saved_jobs", scroll=True
        )

        if extracted.text and extracted.text != RATE_LIMITED_MSG:
            all_text.append(extracted.text)

        page_job_ids = await self._extract_job_ids()
        all_job_ids.extend(page_job_ids)

        # Pagination: click next page until no more jobs
        max_pages = 5
        for page_num in range(2, max_pages + 1):
            clicked = await self._click_next_page(page_num)
            if not clicked:
                break
            await self._page.wait_for_timeout(2000)
            more_ids = await self._extract_job_ids()
            new_ids = [jid for jid in more_ids if jid not in all_job_ids]
            if not new_ids:
                break
            all_job_ids.extend(new_ids)

            page_text = await self._extract_inner_text()
            if page_text:
                all_text.append(page_text)

        sections: dict[str, str] = {}
        section_errors: dict[str, str] = {}

        if all_text:
            sections["saved_jobs"] = "\n--- PAGE BREAK ---\n".join(all_text)
        elif extracted.error:
            section_errors["saved_jobs"] = extracted.error

        result: dict[str, Any] = {"url": JOBS_TRACKER_URL}

        if sections:
            result["sections"] = sections
        if all_job_ids:
            result["job_ids"] = all_job_ids
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
        """Extract job title, company, location from job page.

        Uses resilient text-based parsing from <main> innerText
        since LinkedIn uses auto-generated CSS class names.
        """
        try:
            data = await self._page.evaluate("""
                () => {
                    const result = {title: '', company: '', location: ''};

                    // Company: always linked via /company/ anchor
                    const companyLink = document.querySelector('a[href*="/company/"]');
                    if (companyLink) result.company = companyLink.innerText.trim();

                    // Parse main innerText for title + location
                    const main = document.querySelector('main');
                    if (!main) return result;
                    const raw = main.innerText || '';
                    const blocks = raw.split(/\\n{2,}/).map(b => b.trim()).filter(Boolean);

                    if (blocks.length === 0) return result;

                    // First block is usually the company name
                    // Find title: first block that isn't the company name
                    const comp = result.company;
                    for (const block of blocks) {
                        const line = block.split('\\n')[0].trim();
                        if (line && line !== comp && line.length > 3) {
                            result.title = line;
                            break;
                        }
                    }

                    // Location: look for a block containing Czech city/region
                    const locPatterns = [
                        /Praha/i, /Brno/i, /Ostrava/i, /Plzeň/i,
                        /Česko/i, /Czech/i, /kraj/i, /remote/i,
                        /Jihomoravský/i, /Moravskoslezský/i,
                    ];
                    for (const block of blocks) {
                        for (const pat of locPatterns) {
                            if (pat.test(block)) {
                                result.location = block.split('\\n')[0].trim();
                                break;
                            }
                        }
                        if (result.location) break;
                    }

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

    async def _click_next_page(self, current_page: int = 1) -> bool:
        """Click pagination 'next page' (page current_page + 1) on jobs-tracker.

        Args:
            current_page: Current page number (2 for 2nd page, etc.).

        Returns True if a page turn was detected, False otherwise.
        """
        try:
            await self._scroll_to_bottom()
            await self._page.wait_for_timeout(500)

            target_page = current_page + 1
            clicked = await self._page.evaluate(f"""
                () => {{
                    const allSpans = document.querySelectorAll('span, button, a');
                    const paginationItems = [];

                    for (const el of allSpans) {{
                        const text = el.innerText?.trim();
                        if (!text) continue;
                        if (/^\\d+$/.test(text) || /^(Další|Next|›|»)$/i.test(text)) {{
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {{
                                const style = window.getComputedStyle(el);
                                if (style.display !== 'none' && style.visibility !== 'hidden') {{
                                    paginationItems.push({{el, text, top: rect.top}});
                                }}
                            }}
                        }}
                    }}

                    if (paginationItems.length === 0) return false;

                    // Try to click the next page number
                    const target = paginationItems.find(
                        p => /^\\d+$/.test(p.text) && parseInt(p.text) === {target_page}
                    ) || paginationItems.find(
                        p => /^(Další|Next|›|»)$/i.test(p.text)
                    );

                    if (!target) return false;
                    target.el.click();
                    return true;
                }}
            """)
            if clicked:
                await self._page.wait_for_timeout(2000)
            return bool(clicked)
        except Exception as e:
            logger.warning("Pagination click failed: %s", e)
            return False

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
