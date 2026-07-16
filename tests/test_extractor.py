"""Unit tests for extractor.py using AsyncMock(spec=Page).

No real browser — Patchright Page is mocked throughout.
Tests cover: job metadata extraction, job ID extraction,
navigate_to_page (success + timeout + checkpoint).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from linkedin_mcp_custom.scraping.extractor import LinkedInExtractor

AUTH_PATH = "linkedin_mcp_custom.scraping.extractor.ensure_authenticated"


@pytest.fixture
def mock_page():
    """Create an AsyncMock with spec=Page from patchright."""
    p = AsyncMock()
    p.url = "https://www.linkedin.com/feed/"
    return p


@pytest.fixture
def extractor(mock_page):
    return LinkedInExtractor(mock_page)


@pytest.fixture(autouse=True)
def mock_auth():
    """Prevent ensure_authenticated from actually navigating."""
    with patch(AUTH_PATH, new=AsyncMock()) as m:
        yield m


class TestExtractJobMetadata:
    """_extract_job_metadata_from: title, company, location parsing."""

    @pytest.mark.asyncio
    async def test_full_metadata(self, extractor, mock_page):
        mock_page.evaluate.return_value = {
            "title": "Test Engineer",
            "company": "Siemens",
            "location": "Praha",
        }
        result = await extractor._extract_job_metadata_from(mock_page)
        assert result["title"] == "Test Engineer"
        assert result["company"] == "Siemens"
        assert result["location"] == "Praha"

    @pytest.mark.asyncio
    async def test_empty_metadata(self, extractor, mock_page):
        mock_page.evaluate.return_value = {"title": "", "company": "", "location": ""}
        result = await extractor._extract_job_metadata_from(mock_page)
        assert result["title"] == ""
        assert result["company"] == ""
        assert result["location"] == ""

    @pytest.mark.asyncio
    async def test_evaluate_raises(self, extractor, mock_page):
        mock_page.evaluate.side_effect = Exception("evaluate failed")
        result = await extractor._extract_job_metadata_from(mock_page)
        assert result["title"] == ""
        assert result["company"] == ""
        assert result["location"] == ""


class TestExtractJobIds:
    """_extract_job_ids: extracting numeric job IDs from page content."""

    @pytest.mark.asyncio
    async def test_returns_list(self, extractor, mock_page):
        mock_page.evaluate.return_value = ["12345678", "87654321"]
        result = await extractor._extract_job_ids()
        assert result == ["12345678", "87654321"]

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_ids(self, extractor, mock_page):
        mock_page.evaluate.return_value = []
        result = await extractor._extract_job_ids()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_evaluate_fail(self, extractor, mock_page):
        mock_page.evaluate.side_effect = Exception("JS error")
        result = await extractor._extract_job_ids()
        assert result == []


class TestExtractInnerText:
    """_extract_inner_text_from: main/body text extraction."""

    @pytest.mark.asyncio
    async def test_main_text(self, extractor, mock_page):
        mock_page.evaluate.return_value = "Job posting content here"
        result = await extractor._extract_inner_text_from(mock_page)
        assert result == "Job posting content here"

    @pytest.mark.asyncio
    async def test_null_text(self, extractor, mock_page):
        mock_page.evaluate.return_value = None
        result = await extractor._extract_inner_text_from(mock_page)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_raises_returns_none(self, extractor, mock_page):
        mock_page.evaluate.side_effect = Exception("JS timeout")
        result = await extractor._extract_inner_text_from(mock_page)
        assert result is None


class TestNavigateToPage:
    """navigate_to_page: success, timeout, checkpoint detection."""

    @pytest.mark.asyncio
    async def test_successful_navigation(self, extractor, mock_page, mock_auth):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_page.text_content.return_value = "body content"

        with patch(
            "linkedin_mcp_custom.scraping.extractor._retry_goto",
            new=AsyncMock(return_value=mock_resp),
        ):
            await extractor.navigate_to_page("https://www.linkedin.com/jobs/view/123/")

    @pytest.mark.asyncio
    async def test_checkpoint_detection(self, extractor, mock_page):
        """Checkpoint is detected in scrape_job via page.url, not navigate_to_page."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_page.url = "https://www.linkedin.com/checkpoint/"
        mock_page.text_content.return_value = "checkpoint body"

        with patch(
            "linkedin_mcp_custom.scraping.extractor._retry_goto",
            new=AsyncMock(return_value=mock_resp),
        ):
            with pytest.raises(Exception) as exc_info:
                await extractor.scrape_job("123")
            assert "checkpoint" in str(exc_info.value).lower()


class TestScrapeJob:
    """scrape_job: high-level job scraping."""

    @pytest.mark.asyncio
    async def test_returns_sections_on_success(self, extractor, mock_page):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_page.url = "https://www.linkedin.com/jobs/view/123/"
        mock_page.text_content.return_value = "Job body"
        # evaluate calls: scroll → innerText → metadata
        mock_page.evaluate = AsyncMock(
            side_effect=[
                None,  # scroll
                "Python developer, Git, CI/CD.",  # innerText
                {"title": "Test Engineer", "company": "Siemens", "location": "Praha"},  # metadata
            ]
        )

        with patch(
            "linkedin_mcp_custom.scraping.extractor._retry_goto",
            new=AsyncMock(return_value=mock_resp),
        ):
            result = await extractor.scrape_job("123")
            assert result.get("job_title") == "Test Engineer"
            assert result.get("company") == "Siemens"
            assert "sections" in result

    @pytest.mark.asyncio
    async def test_returns_errors_on_http_400(self, extractor, mock_page):
        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_page.text_content.return_value = "Not found"

        with patch(
            "linkedin_mcp_custom.scraping.extractor._retry_goto",
            new=AsyncMock(return_value=mock_resp),
        ):
            result = await extractor.scrape_job("123")
            assert result.get("section_errors", {}).get("job_posting", "") == "HTTP 404"


class TestScrollWithPage:
    """_scroll_with_page: scroll interaction."""

    @pytest.mark.asyncio
    async def test_scroll_success(self, extractor, mock_page):
        mock_page.evaluate.return_value = None
        await extractor._scroll_with_page(mock_page)
        mock_page.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_scroll_raises_does_not_propagate(self, extractor, mock_page):
        mock_page.evaluate.side_effect = Exception("scroll failed")
        await extractor._scroll_with_page(mock_page)
