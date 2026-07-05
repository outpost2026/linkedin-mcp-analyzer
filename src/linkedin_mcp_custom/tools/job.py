"""MCP tools for LinkedIn saved jobs — scraped, analyzed, scored."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

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
    async def analyze_saved_jobs(ctx: Context) -> dict[str, Any]:
        """Full pipeline: scrape saved jobs -> EROI score -> KB write-back.

        1. Scrapes all saved jobs from LinkedIn
        2. For each job, extracts full details
        3. Runs EROI analysis (domain/tech/role/growth/formal/location)
        4. Detects skill gaps against your portfolio
        5. Writes structured report + metadata to B2B-Knowledge-Base
        6. Git commits the changes
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

            # For each job, get details (scoring comes in Fáze 4)
            results = []
            for jid in job_ids:
                details = await extractor.scrape_job(jid)
                results.append(
                    {
                        "job_id": jid,
                        "url": details.get("url"),
                        "has_content": "sections" in details,
                        "analysis": {
                            "status": "pending",
                            "note": "EROI scoring coming in Fáze 4",
                        },
                    }
                )

            await ctx.info(
                f"Retrieved {len(results)} job postings. "
                "Analysis pipeline ready — EROI engine in next phase."
            )

            return {
                "status": "ok",
                "job_count": len(results),
                "jobs": results,
                "pipeline_phase": "scraping_complete",
                "next": "Run EROI analysis (Fáze 4) for full scoring",
            }

        except AuthenticationError:
            return {
                "status": "auth_required",
                "message": "Session expired. Run: linkedin-mcp --login",
            }
        except Exception as e:
            await ctx.error(f"Pipeline failed: {e}")
            return {"status": "error", "message": str(e)}
