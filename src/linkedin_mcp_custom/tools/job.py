"""MCP tools for LinkedIn saved jobs — scraped, analyzed, scored, KB written."""

from __future__ import annotations

import time
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_custom.analysis.kb_writer import KBWriter
from linkedin_mcp_custom.analysis.schemas import JobFeatures
from linkedin_mcp_custom.analysis.scorer import score_job
from linkedin_mcp_custom.core import (
    AuthenticationError,
    ensure_authenticated,
    get_page,
)
from linkedin_mcp_custom.scraping import LinkedInExtractor

# Time budget: process at most this many seconds per MCP tool call.
# MCP clients typically timeout at 60-120s. We leave headroom for
# auth checks, browser overhead, and JSON serialization.
MAX_BATCH_SECONDS = 45
MIN_BATCH_JOBS = 1


async def _get_extractor(ctx: Context) -> LinkedInExtractor:
    """Get a ready-to-use LinkedInExtractor with authenticated page."""
    page = await get_page()
    await ensure_authenticated(page)
    return LinkedInExtractor(page)


def register_job_tools(mcp: FastMCP) -> None:
    """Register all job-related MCP tools."""

    @mcp.tool(
        title="Get Saved Jobs",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "scraping"},
    )
    async def get_saved_jobs(ctx: Context) -> dict[str, Any]:
        """Get saved jobs from LinkedIn's /jobs-tracker/ page.

        Returns saved jobs raw text and a list of numeric job IDs.
        Pass any job_id to get_job_details or analyze_job.
        """
        await ctx.info("Opening LinkedIn saved jobs tracker...")
        try:
            extractor = await _get_extractor(ctx)
            result = await extractor.scrape_saved_jobs()
            job_count = len(result.get("job_ids", []))
            await ctx.info(f"Found {job_count} saved jobs")
            return result
        except AuthenticationError:
            return {
                "status": "auth_required",
                "message": "Session expired. Run: linkedin-mcp --login",
            }
        except Exception as e:
            await ctx.error(f"Failed to get saved jobs: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool(
        title="Get Job Details",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "scraping"},
    )
    async def get_job_details(job_id: str, ctx: Context) -> dict[str, Any]:
        """Get full details for a specific LinkedIn job posting.

        Args:
            job_id: LinkedIn numeric job ID (e.g. '4252026496').
                    Get these from get_saved_jobs output.
        """
        await ctx.info(f"Fetching job {job_id}...")
        try:
            extractor = await _get_extractor(ctx)
            result = await extractor.scrape_job(job_id)
            if "sections" in result:
                text_len = len(result["sections"].get("job_posting", ""))
                await ctx.info(f"Retrieved job details ({text_len} chars)")
            return result
        except AuthenticationError:
            return {
                "status": "auth_required",
                "message": "Session expired. Run: linkedin-mcp --login",
            }
        except Exception as e:
            await ctx.error(f"Failed to get job details: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool(
        title="Analyze Single Job",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "analysis"},
    )
    async def analyze_job(
        job_id: str,
        ctx: Context,
        write_to_kb: bool = True,
    ) -> dict[str, Any]:
        """Scrape, EROI score, and KB-write a single LinkedIn job.

        Always fits within MCP timeout (~10s per job).
        Call this in a loop from the client for all saved jobs,
        or use analyze_saved_jobs for batching.

        Args:
            job_id: LinkedIn numeric job ID (e.g. '4252026496').
            write_to_kb: If True, writes result to B2B-Knowledge-Base.
        """
        await ctx.info(f"Analyzing job {job_id}...")
        try:
            extractor = await _get_extractor(ctx)
            details = await extractor.scrape_job(job_id)
            sections = details.get("sections", {})
            raw_text = sections.get("job_posting", "")
            if not raw_text:
                return {
                    "status": "error",
                    "message": f"No job posting text for {job_id}",
                    "job_id": job_id,
                }

            title = details.get("job_title", sections.get("job_title", ""))
            company = details.get("company", sections.get("company", ""))
            location = details.get("location", sections.get("location", ""))

            features = JobFeatures(
                raw_text=raw_text,
                job_title=title,
                company=company,
                location=location,
                job_id=job_id,
            )
            eroi = score_job(features)

            result = eroi.to_dict()
            result["status"] = "ok"

            if write_to_kb:
                kb = KBWriter()
                kb.write_all(eroi, raw_text, linkedin_job_id=job_id)
                result["kb_written"] = True
                await ctx.info(
                    f"KB #{eroi.job_id}: {title} @ {company}"
                    f" -> {eroi.total_score}% ({eroi.verdict})"
                )
            else:
                await ctx.info(
                    f"#{job_id}: {title} @ {company} -> {eroi.total_score}% ({eroi.verdict})"
                )

            return result

        except AuthenticationError:
            return {
                "status": "auth_required",
                "message": "Session expired. Run: linkedin-mcp --login",
                "job_id": job_id,
            }
        except Exception as e:
            await ctx.error(f"Failed to analyze job {job_id}: {e}")
            return {"status": "error", "message": str(e), "job_id": job_id}

    @mcp.tool(
        title="Analyze Saved Jobs",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "analysis"},
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
            extractor = await _get_extractor(ctx)
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

            results = []
            kb = KBWriter() if write_to_kb else None
            processed_ids: list[str] = []
            unprocessed_ids: list[str] = []
            errored_ids: list[str] = []

            deadline = time.time() + max_seconds

            for idx, jid in enumerate(all_job_ids):
                if limit > 0 and len(processed_ids) >= limit:
                    unprocessed_ids = all_job_ids[idx:]
                    break

                if time.time() >= deadline:
                    unprocessed_ids = all_job_ids[idx:]
                    await ctx.info(f"Time budget reached, {len(unprocessed_ids)} jobs remaining")
                    break

                try:
                    details = await extractor.scrape_job(jid)
                    sections = details.get("sections", {})
                    raw_text = sections.get("job_posting", "")
                    if not raw_text:
                        errored_ids.append(jid)
                        continue

                    title = details.get("job_title", sections.get("job_title", ""))
                    company = details.get("company", sections.get("company", ""))
                    location = details.get("location", sections.get("location", ""))

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

                    results.append(eroi.to_dict())
                    processed_ids.append(jid)

                    await ctx.info(
                        f"  [{idx + 1}/{len(all_job_ids)}] {title} @ {company}"
                        f" -> {eroi.total_score}% ({eroi.verdict})"
                    )
                except AuthenticationError:
                    unprocessed_ids = all_job_ids[idx:]
                    break
                except Exception as e:
                    await ctx.error(f"Job {jid} failed: {e}")
                    errored_ids.append(jid)

            summary = {
                "total": len(all_job_ids),
                "processed": len(processed_ids),
                "remaining": len(unprocessed_ids),
                "errored": len(errored_ids),
                "sledovat": sum(1 for r in results if r["verdict"] == "SLEDOVAT"),
                "medium": sum(1 for r in results if r["verdict"] == "MEDIUM"),
                "hranicni": sum(1 for r in results if r["verdict"] == "HRANICNI"),
                "nesledovat": sum(1 for r in results if r["verdict"] == "NESLEDOVAT"),
            }

            response: dict[str, Any] = {
                "status": "ok",
                "summary": summary,
                "jobs": results,
                "pipeline_phase": "batch_partial" if unprocessed_ids else "batch_complete",
            }

            if unprocessed_ids:
                response["unprocessed_ids"] = unprocessed_ids
                response["message"] = (
                    f"Processed {len(processed_ids)}/{len(all_job_ids)} jobs. "
                    f"Call analyze_saved_jobs again or use analyze_job per ID for remaining."
                )
            else:
                response["message"] = f"All {len(processed_ids)} jobs analyzed."

            if errored_ids:
                response["errored_ids"] = errored_ids

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
