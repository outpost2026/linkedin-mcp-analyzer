"""Regression test: analyze_saved_jobs must return within max_seconds.

Reproduces the MCP transport timeout bug (-32001) where the batch
pipeline used asyncio.gather over the whole job list, blocking the
response until every job finished (100-250s for 50 jobs).

The fixed version processes jobs sequentially with an early-exit
deadline check *before* each job, guaranteeing a response within
max_seconds.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client, FastMCP
from linkedin_mcp_custom.tools.job import register_job_tools


def _make_extractor(sleep_per_job: float, n_jobs: int):
    """Build a fake LinkedInExtractor whose scrape_job is slow + serial."""
    extractor = MagicMock()

    async def _fake_scrape(job_id, parallel=False, delay_between=0.0):
        await asyncio.sleep(sleep_per_job)
        return {
            "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
            "job_title": f"Job {job_id}",
            "company": "TestCo",
            "location": "Praha",
            "sections": {
                "job_posting": (
                    "Python developer, Git, CI/CD, industrial automation, "
                    "PLC, embedded, AI integration, machine vision."
                )
            },
        }

    extractor.scrape_saved_jobs = AsyncMock(
        return_value={"job_ids": [str(i) for i in range(n_jobs)]}
    )
    extractor.scrape_job = _fake_scrape
    return extractor


@pytest.mark.asyncio
async def test_batch_returns_within_deadline():
    """50 slow jobs (1s each) with 10s budget -> response under ~11s."""
    mcp = FastMCP("test")
    register_job_tools(mcp)

    fake = _make_extractor(sleep_per_job=1.0, n_jobs=50)
    kb_fake = MagicMock()
    kb_fake.write_all.return_value = {"status": "ok", "entry_id": "x"}

    with (
        patch(
            "linkedin_mcp_custom.tools.job.LinkedInExtractor",
            return_value=fake,
        ),
        patch("linkedin_mcp_custom.tools.job.KBWriter", return_value=kb_fake),
        patch(
            "linkedin_mcp_custom.tools.job.get_page",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "linkedin_mcp_custom.tools.job.ensure_authenticated",
            AsyncMock(),
        ),
    ):
        async with Client(mcp) as client:
            start = time.time()
            result = await client.call_tool(
                "analyze_saved_jobs",
                {"write_to_kb": True, "max_seconds": 10, "limit": 0},
            )
            elapsed = time.time() - start

    data = result.data
    assert elapsed < 12, f"Batch took {elapsed:.1f}s — exceeded deadline budget"
    assert data["status"] == "ok"
    # With 1s/job and 10s budget we should process ~10, not all 50.
    assert data["summary"]["processed"] <= 11, data["summary"]
    assert data["summary"]["processed"] >= 8, data["summary"]
    # Remaining jobs must be reported for follow-up.
    assert data["summary"]["remaining"] > 0
    assert len(data["unprocessed_ids"]) == data["summary"]["remaining"]


@pytest.mark.asyncio
async def test_batch_respects_limit():
    """limit=3 -> exactly 3 processed, rest unprocessed."""
    mcp = FastMCP("test")
    register_job_tools(mcp)

    fake = _make_extractor(sleep_per_job=0.1, n_jobs=50)
    kb_fake = MagicMock()
    kb_fake.write_all.return_value = {"status": "ok"}

    with (
        patch(
            "linkedin_mcp_custom.tools.job.LinkedInExtractor",
            return_value=fake,
        ),
        patch("linkedin_mcp_custom.tools.job.KBWriter", return_value=kb_fake),
        patch(
            "linkedin_mcp_custom.tools.job.get_page",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "linkedin_mcp_custom.tools.job.ensure_authenticated",
            AsyncMock(),
        ),
    ):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "analyze_saved_jobs",
                {"write_to_kb": False, "max_seconds": 100, "limit": 3},
            )

    data = result.data
    assert data["summary"]["processed"] == 3
    assert data["summary"]["remaining"] == 47


@pytest.mark.asyncio
async def test_batch_no_sequential_gather_hang():
    """Even with a very small budget the call returns fast (no gather block)."""
    mcp = FastMCP("test")
    register_job_tools(mcp)

    fake = _make_extractor(sleep_per_job=2.0, n_jobs=50)
    kb_fake = MagicMock()
    kb_fake.write_all.return_value = {"status": "ok"}

    with (
        patch(
            "linkedin_mcp_custom.tools.job.LinkedInExtractor",
            return_value=fake,
        ),
        patch("linkedin_mcp_custom.tools.job.KBWriter", return_value=kb_fake),
        patch(
            "linkedin_mcp_custom.tools.job.get_page",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "linkedin_mcp_custom.tools.job.ensure_authenticated",
            AsyncMock(),
        ),
    ):
        async with Client(mcp) as client:
            start = time.time()
            result = await client.call_tool(
                "analyze_saved_jobs",
                {"write_to_kb": False, "max_seconds": 1, "limit": 0},
            )
            elapsed = time.time() - start

    assert elapsed < 5, f"Tiny budget still hung for {elapsed:.1f}s"
    data = result.data
    assert data["summary"]["processed"] >= 0
    assert data["pipeline_phase"] == "batch_partial"


@pytest.mark.asyncio
async def test_batch_job_ids_continuation():
    """job_ids param feeds back unprocessed_ids — saved-jobs scrape skipped."""
    mcp = FastMCP("test")
    register_job_tools(mcp)

    fake = _make_extractor(sleep_per_job=0.1, n_jobs=50)
    kb_fake = MagicMock()
    kb_fake.write_all.return_value = {"status": "ok"}

    with (
        patch(
            "linkedin_mcp_custom.tools.job.LinkedInExtractor",
            return_value=fake,
        ),
        patch("linkedin_mcp_custom.tools.job.KBWriter", return_value=kb_fake),
        patch(
            "linkedin_mcp_custom.tools.job.get_page",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "linkedin_mcp_custom.tools.job.ensure_authenticated",
            AsyncMock(),
        ),
    ):
        async with Client(mcp) as client:
            first = await client.call_tool(
                "analyze_saved_jobs",
                {"write_to_kb": False, "max_seconds": 1, "limit": 0},
            )
            first_data = first.data
            assert first_data["pipeline_phase"] == "batch_partial"
            assert first_data["unprocessed_ids"]

            # The first call legitimately scrapes saved jobs; reset so we
            # can assert the continuation call skips the scrape.
            fake.scrape_saved_jobs.reset_mock()

            # Feed the unprocessed IDs back — must process exactly those.
            second = await client.call_tool(
                "analyze_saved_jobs",
                {
                    "write_to_kb": False,
                    "max_seconds": 100,
                    "limit": 0,
                    "job_ids": first_data["unprocessed_ids"],
                },
            )
            second_data = second.data

    # Saved-jobs scrape must be skipped when job_ids is supplied.
    fake.scrape_saved_jobs.assert_not_called()
    # The continuation call processes exactly the IDs we passed.
    assert second_data["summary"]["processed"] == len(first_data["unprocessed_ids"])
    assert second_data["summary"]["remaining"] == 0
    assert second_data["pipeline_phase"] == "batch_complete"
