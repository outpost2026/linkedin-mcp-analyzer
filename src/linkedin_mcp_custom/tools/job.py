"""MCP tools for LinkedIn job operations — scrape, score, KB write-back."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastmcp import Context

from linkedin_mcp_custom.analysis.kb_writer import KBWriter
from linkedin_mcp_custom.analysis.schemas import JobFeatures
from linkedin_mcp_custom.analysis.scorer import score_job
from linkedin_mcp_custom.core import (
    AuthenticationError,
    ensure_authenticated,
    get_page,
)
from linkedin_mcp_custom.scraping import LinkedInExtractor

logger = logging.getLogger(__name__)

MAX_BATCH_SECONDS = 45
DEFAULT_MAX_CONCURRENT = 3
DEFAULT_DELAY_BETWEEN = 1.5


def register_job_tools(mcp: Any) -> None:
    """Register all job-related MCP tools."""

    async def _get_extractor() -> LinkedInExtractor:
        """Get initialized extractor with authenticated page."""
        page = await get_page()
        await ensure_authenticated(page)
        return LinkedInExtractor(page)

    # ── tool: get_saved_jobs ────────────────────────────────────────

    @mcp.tool(
        tags={"scrape", "jobs"},
    )
    async def get_saved_jobs() -> dict[str, Any]:
        """Get saved jobs from LinkedIn's /jobs-tracker/ page.

        Returns saved jobs raw text and a list of numeric job IDs.
        Pass any job_id to get_job_details or analyze_job.
        """
        extractor = await _get_extractor()
        result = await extractor.scrape_saved_jobs()
        job_ids = result.get("job_ids", [])
        return {
            "job_ids": job_ids,
            "job_ids_count": len(job_ids),
            "raw_text": (result.get("sections", {}) or {}).get("saved_jobs", ""),
        }

    # ── tool: get_job_details ───────────────────────────────────────

    @mcp.tool(
        tags={"scrap", "jobs"},
    )
    async def get_job_details(job_id: str) -> dict[str, Any]:
        """Get full details for a specific LinkedIn job posting."""
        extractor = await _get_extractor()
        result = await extractor.scrape_job(job_id)
        return {
            "url": result.get("url", ""),
            "job_title": result.get("job_title", ""),
            "company": result.get("company", ""),
            "location": result.get("location", ""),
            "raw_text": (result.get("sections", {}) or {}).get("job_posting", ""),
        }

    # ── tool: analyze_job ───────────────────────────────────────────

    @mcp.tool(
        tags={"analysis", "jobs"},
    )
    async def analyze_job(
        job_id: str,
        write_to_kb: bool = True,
    ) -> dict[str, Any]:
        """Scrape, EROI score, and KB-write a single LinkedIn job.

        Always fits within MCP timeout (~10s per job).
        Call this in a loop from the client for all saved jobs,
        or use analyze_saved_jobs for batching.
        """
        extractor = await _get_extractor()
        detail = await extractor.scrape_job(job_id)
        sections = detail.get("sections", {})
        raw_text = sections.get("job_posting", "")
        if not raw_text:
            return {"status": "error", "message": "No job posting text found"}

        title = detail.get("job_title", sections.get("job_title", ""))
        company = detail.get("company", sections.get("company", ""))
        location = detail.get("location", sections.get("location", ""))

        features = JobFeatures(
            raw_text=raw_text,
            job_title=title,
            company=company,
            location=location,
            job_id=job_id,
        )
        eroi = score_job(features)

        write_result: dict[str, Any] | None = None
        if write_to_kb:
            kb = KBWriter()
            write_result = kb.write_all(eroi, raw_text, linkedin_job_id=job_id)

        result = eroi.to_dict()
        result["kb_write"] = write_result
        return result

    # ── tool: analyze_saved_jobs (batch) ─────────────────────────────

    @mcp.tool(
        tags={"analysis", "jobs", "batch"},
    )
    async def analyze_saved_jobs(
        ctx: Context,
        write_to_kb: bool = True,
        max_seconds: int = MAX_BATCH_SECONDS,
        limit: int = 0,
    ) -> dict[str, Any]:
        """Batch pipeline: scrape saved jobs -> EROI score -> KB write-back.

        Processes as many jobs as fit within max_seconds (default 45s)
        to avoid MCP transport timeout. Returns partial results with
        unprocessed job IDs for follow-up calls.

        For full batch processing across all jobs, use the CLI script:
          .venv\\Scripts\\python scripts\\run_pipeline.py

        Args:
            write_to_kb: If True, appends results to B2B-Knowledge-Base.
            max_seconds: Max wall-clock seconds for this batch (default 45).
            limit: Max jobs to process (0 = unlimited within time budget).
        """
        await ctx.info("Starting batch analysis pipeline...")

        try:
            extractor = await _get_extractor()
            saved = await extractor.scrape_saved_jobs()
            all_job_ids = saved.get("job_ids", [])

            if not all_job_ids:
                return {
                    "status": "ok",
                    "message": "No saved jobs found to analyze.",
                    "job_ids": [],
                }

            await ctx.info(
                f"Found {len(all_job_ids)} saved jobs, processing within {max_seconds}s budget"
            )

            kb = KBWriter() if write_to_kb else None
            processed_ids: list[str] = []
            unprocessed_ids: list[str] = []
            errored_ids: list[str] = []
            deadline_skipped_ids: list[str] = []

            deadline = time.time() + max_seconds
            # Gentle parallel scraping with semaphore + staggered delays
            results: list[dict[str, Any]] = []
            semaphore = asyncio.Semaphore(DEFAULT_MAX_CONCURRENT)
            stagger_step = DEFAULT_DELAY_BETWEEN / max(DEFAULT_MAX_CONCURRENT, 1)

            async def _scrape_one(k: int, jid: str) -> dict[str, Any] | None:
                stagger_delay = min(k * stagger_step, 2.0)
                if stagger_delay > 0:
                    await asyncio.sleep(stagger_delay)

                async with semaphore:
                    if time.time() >= deadline:
                        return {"__deadline__": True}
                    try:
                        detail = await extractor.scrape_job(jid, parallel=True)
                        raw_text = (detail.get("sections", {}) or {}).get("job_posting", "")
                        if not raw_text:
                            return None

                        title = detail.get("job_title", "")
                        company = detail.get("company", "")
                        location = detail.get("location", "")
                        features = JobFeatures(
                            raw_text=raw_text,
                            job_title=title,
                            company=company,
                            location=location,
                            job_id=jid,
                        )
                        eroi = score_job(features)
                        if kb:
                            kb.write_all(eroi, raw_text, linkedin_job_id=jid)

                        result = eroi.to_dict()
                        await ctx.info(
                            f"  #{jid}: {result.get('job_title', '?')} @ "
                            f"{result.get('company', '?')} -> "
                            f"{result.get('total_score', '?')}% ({result.get('verdict', '?')})"
                        )
                        return result
                    except AuthenticationError:
                        raise
                    except Exception:
                        return None

            # Slice to limit
            job_ids_to_process = all_job_ids[:limit] if limit > 0 else all_job_ids
            tasks = [_scrape_one(idx, jid) for idx, jid in enumerate(job_ids_to_process)]
            results_list = await asyncio.gather(*tasks)

            for jid, r in zip(job_ids_to_process, results_list):
                if r is None:
                    errored_ids.append(jid)
                elif r.get("__deadline__"):
                    deadline_skipped_ids.append(jid)
                else:
                    results.append(r)
                    processed_ids.append(jid)

            # IDs beyond limit are "unprocessed"
            if limit > 0 and len(all_job_ids) > limit:
                unprocessed_ids = all_job_ids[limit:]

            summary = {
                "total": len(all_job_ids),
                "processed": len(processed_ids),
                "remaining": len(unprocessed_ids),
                "deadline_skipped": len(deadline_skipped_ids),
                "errored": len(errored_ids),
                "sledovat": sum(1 for r in results if r.get("verdict") == "SLEDOVAT"),
                "medium": sum(1 for r in results if r.get("verdict") == "MEDIUM"),
                "hranicni": sum(1 for r in results if r.get("verdict") == "HRANICNI"),
                "nesledovat": sum(1 for r in results if r.get("verdict") == "NESLEDOVAT"),
            }

            response: dict[str, Any] = {
                "status": "ok",
                "summary": summary,
                "jobs": results,
                "jobs_count": len(results),
                "pipeline_phase": "batch_partial" if unprocessed_ids else "batch_complete",
                "parallel_config": {
                    "max_concurrent": DEFAULT_MAX_CONCURRENT,
                    "delay_between": DEFAULT_DELAY_BETWEEN,
                },
            }

            if unprocessed_ids:
                response["unprocessed_ids"] = unprocessed_ids
                response["message"] = (
                    f"Processed {len(processed_ids)}/{len(all_job_ids)} jobs "
                    f"({len(unprocessed_ids)} remaining). "
                    f"Call analyze_saved_jobs again or use analyze_job per ID for remaining."
                )
            else:
                response["message"] = f"All {len(processed_ids)} jobs analyzed."

            if errored_ids:
                response["errored_ids"] = errored_ids
            if deadline_skipped_ids:
                response["deadline_skipped_ids"] = deadline_skipped_ids

            if kb:
                response["kb_written"] = True

            return response

        except AuthenticationError:
            return {
                "status": "auth_required",
                "message": "Session expired. Run: linkedin-mcp --login",
            }
        except Exception as e:
            await ctx.error(f"Pipeline failed: {e}")
            return {"status": "error", "message": str(e)}
