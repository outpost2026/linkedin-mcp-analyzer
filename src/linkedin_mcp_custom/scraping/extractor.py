"""LinkedInExtractor — navigate, scroll, extract innerText, strip noise."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from patchright.async_api import Page

from linkedin_mcp_custom.core.auth import check_cached_auth, ensure_authenticated
from linkedin_mcp_custom.core.browser import create_page
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

# Rate-limit adaptive backoff state
_rate_limit_hits: list[float] = []


def _record_rate_limit_hit() -> None:
    global _rate_limit_hits
    _rate_limit_hits.append(asyncio.get_event_loop().time())


def _is_navigation_race(error_msg: str) -> bool:
    """Detect transient navigation race conditions.

    These occur when multiple concurrent page.goto() calls happen
    on the same Page instance, or when Chromium cancels a navigation.
    Safe to retry — the error is about timing, not the target page.
    """
    return any(p in error_msg for p in ["ERR_ABORTED", "interrupted by another navigation"])


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

    # ── Page pool helpers ────────────────────────────────────────────

    async def get_page_for_scrape(self) -> Page:
        """Get a page from the pool for parallel scraping."""
        return await create_page()

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

    async def scrape_job(
        self,
        job_id: str,
        parallel: bool = False,
        delay_between: float = 0.0,
    ) -> dict[str, Any]:
        """Scrape full job posting details with structured fields.

        Args:
            job_id: LinkedIn numeric job ID (e.g. "4252026496").
            parallel: If True, uses pooled pages for concurrent scraping.
                      If False, uses the singleton page (existing behavior).
            delay_between: Minimum delay in seconds before scraping this job
                           (for LinkedIn-friendly rate limiting).

        Returns:
            Dict with url, sections, job_title, company, location.
            The 'job_posting' section contains the full raw text.
        """
        if delay_between > 0:
            await asyncio.sleep(delay_between)

        # Use pooled page for parallel, singleton for sequential
        page = await self.get_page_for_scrape() if parallel else self._page

        # For parallel scraping: check cached auth without navigating
        # (avoids racing with pooled page's own navigation)
        # If cache is stale, log a warning but proceed — cookies are valid
        # in the persistent profile. Navigating the singleton page from
        # parallel tasks causes ERR_ABORTED races on the shared Page.
        if parallel and not check_cached_auth():
            logger.debug(
                "Auth cache stale for job %s — checking after navigation (expected in long runs)",
                job_id,
            )

        url = f"{JOB_VIEW_URL}{job_id}/"

        logger.info("Navigating to %s (page=%s)", url, id(page))

        # Retry loop for transient navigation races (ERR_ABORTED, interrupted)
        max_nav_retries = 2
        last_error: str | None = None
        for attempt in range(max_nav_retries):
            try:
                if not parallel:
                    await ensure_authenticated(page)
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Detect auth redirects regardless of parallel/sequential mode
                current_url = page.url
                if "/login" in current_url:
                    raise AuthenticationError(
                        "Not authenticated — redirected to login. Run: linkedin-mcp --login"
                    )
                if "/checkpoint/" in current_url or "/challenge/" in current_url:
                    raise AuthenticationError(
                        f"LinkedIn checkpoint/challenge page at: {current_url}. "
                        "Run: linkedin-mcp --login"
                    )

                if resp and resp.status >= 400:
                    body = await page.text_content("body") or ""
                    if is_rate_limited(body):
                        _record_rate_limit_hit()
                        return {
                            "url": url,
                            "job_title": "",
                            "company": "",
                            "location": "",
                            "section_errors": {"job_posting": "Rate limited"},
                        }
                    return {
                        "url": url,
                        "job_title": "",
                        "company": "",
                        "location": "",
                        "section_errors": {"job_posting": f"HTTP {resp.status}"},
                    }
                await page.wait_for_timeout(2000)
                last_error = None
                break  # navigation success
            except AuthenticationError:
                raise
            except Exception as e:
                last_error = str(e)
                if attempt < max_nav_retries - 1 and _is_navigation_race(str(e)):
                    delay = 1.0 * (attempt + 1)
                    logger.warning(
                        "Navigation race on %s, retrying in %.1fs (attempt %d/%d)",
                        url,
                        delay,
                        attempt + 2,
                        max_nav_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
                # Non-retryable error — fall through to return

        if last_error:
            return {
                "url": url,
                "job_title": "",
                "company": "",
                "location": "",
                "section_errors": {"job_posting": last_error},
            }

        if True:
            await self._scroll_with_page(page)

        raw_text = await self._extract_inner_text_from(page)
        if raw_text and is_rate_limited(raw_text):
            return {
                "url": url,
                "job_title": "",
                "company": "",
                "location": "",
                "section_errors": {"job_posting": "Rate limited"},
            }

        metadata = await self._extract_job_metadata_from(page)

        sections: dict[str, str] = {}
        section_errors: dict[str, str] = {}

        if raw_text and raw_text.strip():
            sections["job_posting"] = strip_noise(raw_text)
        else:
            section_errors["job_posting"] = "No content found"

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

        # Pagination: click "Další" / "Next" button until no more pages
        max_pages = 5
        for _ in range(2, max_pages + 1):
            clicked = await self._click_next_page()
            if not clicked:
                break
            # Wait for content transition (SPA replaces DOM)
            await self._page.wait_for_timeout(3000)
            try:
                await self._page.wait_for_selector(
                    'ul[class*="jobs"] a[href*="/jobs/view/"]', timeout=10000
                )
            except Exception:
                logger.info("Specific job list selector not found, using general")
            page_ids = await self._extract_job_ids()
            all_job_ids.extend(page_ids)

            page_text = await self._extract_inner_text()
            if page_text:
                all_text.append(page_text)

        # Deduplicate at the end (preserve order)
        seen: set[str] = set()
        deduped: list[str] = []
        for jid in all_job_ids:
            if jid not in seen:
                seen.add(jid)
                deduped.append(jid)
        all_job_ids[:] = deduped

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

    # ── Internal helpers (page-parameterized for parallel support) ──

    async def _extract_inner_text_from(self, page: Page) -> str | None:
        """Extract innerText from <main> or <body> as fallback on a given page."""
        try:
            text = await page.evaluate(r"""
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

    async def _extract_inner_text(self) -> str | None:
        """Extract innerText from singleton page (sequential calls)."""
        return await self._extract_inner_text_from(self._page)

    async def _extract_job_ids(self) -> list[str]:
        """Extract all unique LinkedIn job IDs from the current page."""
        try:
            ids = await self._page.evaluate(r"""
                () => {
                    const seen = new Set();
                    const result = [];

                    const addID = (id) => {
                        if (!/^\d{8,}$/.test(id)) return;
                        if (seen.has(id)) return;
                        seen.add(id);
                        result.push(id);
                    };

                    for (const el of document.querySelectorAll('[href*="/jobs/view/"]')) {
                        const m = (el.href || el.getAttribute('href') || '')
                            .match(/\/jobs\/view\/(\d{8,})/);
                        if (m) addID(m[1]);
                    }

                    for (const el of document.querySelectorAll('*')) {
                        for (const attr of el.attributes) {
                            const v = String(attr.value);
                            let m = v.match(/urn:li:jobPosting:(\d{8,})/);
                            if (m) { addID(m[1]); continue; }
                            m = v.match(/\/jobs\/view\/(\d{8,})/);
                            if (m) { addID(m[1]); continue; }
                            m = v.match(/job.*?(\d{10})/i);
                            if (m) { addID(m[1]); continue; }
                        }
                    }

                    for (const script of document.querySelectorAll('script:not([src])')) {
                        const text = script.textContent || '';
                        const matches = [...text.matchAll(/(?<!\d)(\d{10})(?!\d)/g)];
                        for (const m of matches) {
                            const idx = m.index;
                            const before = text.substring(Math.max(0, idx - 40), idx);
                            const after = text.substring(idx + 10, idx + 50);
                            const ctx = before + after;
                            if (/job|posting|saved|tracker|entity/i.test(ctx)) {
                                addID(m[1]);
                            }
                        }
                    }

                    const html = document.documentElement.outerHTML;
                    const htmlMatches = [...html.matchAll(/\/jobs\/view\/(\d{8,})/g)];
                    for (const m of htmlMatches) addID(m[1]);

                    return result;
                }
            """)
            return list(ids) if isinstance(ids, list) else []
        except Exception as e:
            logger.warning("Job ID extraction failed: %s", e)
            return []

    async def _extract_job_metadata_from(self, page: Page) -> dict[str, str]:
        """Extract job title, company, location from a given page."""
        try:
            data = await page.evaluate(r"""
                () => {
                    const result = {title: '', company: '', location: ''};

                    const companyLink = document.querySelector('a[href*="/company/"]');
                    if (companyLink) result.company = companyLink.innerText.trim();

                    const main = document.querySelector('main');
                    if (!main) return result;
                    const raw = main.innerText || '';
                    const blocks = raw.split(/\n{2,}/).map(b => b.trim()).filter(Boolean);

                    if (blocks.length === 0) return result;

                    const comp = result.company;
                    for (const block of blocks) {
                        const line = block.split('\n')[0].trim();
                        if (line && line !== comp && line.length > 3) {
                            result.title = line;
                            break;
                        }
                    }

                    const locPatterns = [
                        /Praha/i, /Brno/i, /Ostrava/i, /Plzeň/i,
                        /Česko/i, /Czech/i, /kraj/i, /remote/i,
                        /Jihomoravský/i, /Moravskoslezský/i,
                    ];
                    for (const block of blocks) {
                        for (const pat of locPatterns) {
                            if (pat.test(block)) {
                                result.location = block.split('\n')[0].trim();
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

    async def _extract_job_metadata(self) -> dict[str, str]:
        """Extract metadata from singleton page (sequential calls)."""
        return await self._extract_job_metadata_from(self._page)

    async def _scroll_with_page(self, page: Page) -> None:
        """Scroll a given page to bottom to trigger lazy loading."""
        try:
            await page.evaluate(r"""
                () => {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            """)
            await page.wait_for_timeout(1500)
        except Exception as e:
            logger.warning("Scroll failed: %s", e)

    async def _scroll_to_bottom(self) -> None:
        """Scroll singleton page to bottom."""
        await self._scroll_with_page(self._page)

    async def _click_next_page(self) -> bool:
        """Click the 'Další / Next' pagination button on jobs-tracker."""
        try:
            await self._scroll_to_bottom()
            await self._page.wait_for_timeout(500)

            clicked = await self._page.evaluate(r"""
                () => {
                    const bySelector = document.querySelector(
                        'span.cf719dd1._076af65a.dec34939.b87'
                    );
                    if (bySelector) {
                        const rect = bySelector.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            const style = window.getComputedStyle(bySelector);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                bySelector.click();
                                return true;
                            }
                        }
                    }

                    const allEls = document.querySelectorAll('span, button, a');
                    for (const el of allEls) {
                        const text = el.innerText?.trim();
                        if (!text) continue;
                        if (!/^(Další|Next|›|»)$/i.test(text)) continue;
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            const style = window.getComputedStyle(el);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                el.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """)
            if clicked:
                await self._page.wait_for_timeout(2000)
            return bool(clicked)
        except Exception as e:
            logger.warning("Pagination click failed: %s", e)
            return False
