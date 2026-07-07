"""MCP tools for LinkedIn saved jobs — scraped, analyzed, scored, KB written."""

from __future__ import annotations

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
        Pass any job_id to get_job_details for full posting text.
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
        title="Analyze Saved Jobs",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "analysis"},
    )
    async def analyze_saved_jobs(
        ctx: Context,
        write_to_kb: bool = True,
    ) -> dict[str, Any]:
        """Full pipeline: scrape saved jobs -> EROI score -> KB write-back.

        1. Scrapes all saved jobs from LinkedIn
        2. For each job, extracts full details
        3. Runs EROI analysis (domain/tech/role/growth/formal/location)
        4. Detects skill gaps against your portfolio
        5. Writes structured report + metadata to B2B-Knowledge-Base
        6. Git commits the changes

        Args:
            write_to_kb: If True, appends results to B2B-Knowledge-Base repo.
        """
        await ctx.info("Starting full analysis pipeline...")

        try:
            extractor = await _get_extractor(ctx)
            saved = await extractor.scrape_saved_jobs()
            job_ids = saved.get("job_ids", [])

            if not job_ids:
                return {
                    "status": "ok",
                    "message": "No saved jobs found to analyze.",
                    "job_ids": [],
                }

            await ctx.info(f"Found {len(job_ids)} jobs to analyze")

            results = []
            kb = KBWriter() if write_to_kb else None

            for jid in job_ids:
                details = await extractor.scrape_job(jid)
                sections = details.get("sections", {})
                raw_text = sections.get("job_posting", "")
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
                    msg = (
                        f"  KB #{eroi.job_id}: {title} @ {company}"
                        f" -> {eroi.total_score}% ({eroi.verdict})"
                    )
                    await ctx.info(msg)
                else:
                    await ctx.info(
                        f"  #{jid}: {title} @ {company} -> {eroi.total_score}% ({eroi.verdict})"
                    )

                results.append(eroi.to_dict())

            summary = {
                "total": len(results),
                "sledovat": sum(1 for r in results if r["verdict"] == "SLEDOVAT"),
                "medium": sum(1 for r in results if r["verdict"] == "MEDIUM"),
                "hranicni": sum(1 for r in results if r["verdict"] == "HRANICNI"),
                "nesledovat": sum(1 for r in results if r["verdict"] == "NESLEDOVAT"),
            }

            await ctx.info(
                f"Analysis complete: {summary['sledovat']} SLEDOVAT, "
                f"{summary['medium']} MEDIUM, {summary['hranicni']} HRANICNI, "
                f"{summary['nesledovat']} NESLEDOVAT"
            )

            response = {
                "status": "ok",
                "job_count": len(results),
                "summary": summary,
                "jobs": results,
                "pipeline_phase": "eroi_complete",
            }
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
