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
        job_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Batch pipeline: scrape saved jobs -> EROI score -> KB write-back.

        Processes jobs sequentially with an early-exit deadline check
        *before* each job, so the MCP transport always gets a response
        within max_seconds (default 45s) — no asyncio.gather over the
        whole batch, which previously caused MCP timeout (-32001).
        Returns partial results with unprocessed job IDs for follow-up
        calls.

        Feed the returned `unprocessed_ids` back via the `job_ids`
        argument to continue a batch across multiple calls (the loop
        described in the FIX report). When `job_ids` is supplied, the
        saved-jobs scrape is skipped entirely.

        For full batch processing across all jobs, use the CLI script:
          .venv\\Scripts\\python scripts\\run_pipeline.py

        Args:
            write_to_kb: If True, appends results to B2B-Knowledge-Base.
            max_seconds: Max wall-clock seconds for this batch (default 45).
            limit: Max jobs to process (0 = unlimited within time budget).
            job_ids: Explicit job ID list to process. If omitted, the
                saved-jobs page is scraped to obtain the IDs. Pass the
                previous response's `unprocessed_ids` to continue.
        """
        await ctx.info("Starting batch analysis pipeline...")

        try:
            extractor = await _get_extractor()
            deadline = time.time() + max_seconds

            if job_ids is not None:
                all_job_ids = list(job_ids)
            else:
                # Bound the initial saved-jobs scrape by the time budget so the
                # whole call can never exceed max_seconds (and thus the MCP
                # transport timeout). Previously this was unbounded and could
                # hang >120s when LinkedIn was slow/rate-limited.
                remaining = deadline - time.time()
                try:
                    saved = await asyncio.wait_for(extractor.scrape_saved_jobs(), timeout=remaining)
                    all_job_ids = saved.get("job_ids", [])
                except TimeoutError:
                    return {
                        "status": "ok",
                        "message": (
                            "Saved-jobs scrape exceeded time budget; "
                            "pass job_ids explicitly to continue."
                        ),
                        "job_ids": [],
                    }

            if not all_job_ids:
                return {
                    "status": "ok",
                    "message": (
                        "No job IDs to analyze."
                        if job_ids is not None
                        else "No saved jobs found to analyze."
                    ),
                    "job_ids": [],
                }

            await ctx.info(
                f"Found {len(all_job_ids)} saved jobs, processing within {max_seconds}s budget"
            )

            kb = KBWriter() if write_to_kb else None
            processed_ids: list[str] = []
            unprocessed_ids: list[str] = []
            errored_ids: list[str] = []

            # Sequential early-exit loop: process one job at a time and
            # abort *before* starting a new one once the deadline is hit.
            # This guarantees the MCP transport gets a response within
            # max_seconds. The previous asyncio.gather(*tasks) over the
            # whole batch blocked the response until every job finished
            # (100-250s for 50 jobs) -> MCP transport timeout (-32001).
            results: list[dict[str, Any]] = []
            job_ids_to_process = all_job_ids[:limit] if limit > 0 else all_job_ids

            for jid in job_ids_to_process:
                # Re-check the budget *before* each job, and never let a single
                # job exceed the remaining budget: a rate-limited/blocked scrape
                # could otherwise hang for 60s+ (2x 30s nav timeout) and push the
                # whole call past the MCP transport timeout (-32001).
                remaining = deadline - time.time()
                if remaining <= 1:
                    unprocessed_ids.append(jid)
                    continue
                try:
                    try:
                        detail = await asyncio.wait_for(
                            extractor.scrape_job(jid, parallel=True, delay_between=1.0),
                            timeout=remaining,
                        )
                    except TimeoutError:
                        logger.warning("Job %s exceeded per-job time budget", jid)
                        errored_ids.append(jid)
                        continue
                    raw_text = (detail.get("sections", {}) or {}).get("job_posting", "")
                    if not raw_text:
                        errored_ids.append(jid)
                        continue

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
                    results.append(result)
                    processed_ids.append(jid)
                    await ctx.info(
                        f"  #{jid}: {result.get('job_title', '?')} @ "
                        f"{result.get('company', '?')} -> "
                        f"{result.get('total_score', '?')}% ({result.get('verdict', '?')})"
                    )
                except AuthenticationError:
                    raise
                except Exception as exc:
                    logger.warning("Job %s failed: %s", jid, exc)
                    errored_ids.append(jid)
                    continue

            # IDs beyond limit are "unprocessed"
            if limit > 0 and len(all_job_ids) > limit:
                unprocessed_ids.extend(all_job_ids[limit:])

            summary = {
                "total": len(all_job_ids),
                "processed": len(processed_ids),
                "remaining": len(unprocessed_ids),
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
                "batch_mode": {
                    "strategy": "sequential_early_exit",
                    "max_seconds": max_seconds,
                    "limit": limit,
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

    # ── tool: generate_report ────────────────────────────────────────

    @mcp.tool(
        tags={"analysis", "report"},
    )
    async def generate_report() -> dict[str, Any]:
        """Generate synthetic report from existing metadata_stacku.json.

        Reads metadata_stacku.json from B2B-Knowledge-Base, computes
        statistics (verdict distribution, skill frequency, SNR, mismatch
        stats, clusters), and writes synteticky_report_{date}.md +
        synthetic_report_{date}.json to the KB LinkedIn directory.

        No browser or LinkedIn auth required — purely computational.
        """
        from linkedin_mcp_custom.analysis.report_generator import (
            SyntheticReportGenerator,
        )

        try:
            gen = SyntheticReportGenerator()
            md_path, json_path = gen.generate()
            return {
                "status": "ok",
                "md_report": str(md_path),
                "json_report": str(json_path),
                "entries_count": len(gen.load_metadata()),
            }
        except Exception as e:
            logger.error("Report generation failed: %s", e)
            return {"status": "error", "message": str(e)}
