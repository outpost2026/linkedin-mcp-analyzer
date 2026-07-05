"""LinkedIn MCP Custom Server — FastMCP entry point."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_custom import __version__
from linkedin_mcp_custom.core import (
    AuthenticationError,
    RateLimitError,
    close_session,
    ensure_authenticated,
    get_or_create_browser,
    get_page,
)

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with all tools."""
    mcp = FastMCP(
        "linkedin-mcp-custom",
        version=__version__,
        instructions=(
            "LinkedIn saved jobs analysis server. "
            "Scrapes saved jobs from /jobs-tracker/, scores them using EROI "
            "golden rules (domain 35%, tech 25%, role 20%, growth 10%, "
            "formal 5%, location 5%), and writes results to B2B-Knowledge-Base."
        ),
    )

    @mcp.tool(
        title="Health Check",
        annotations={"readOnlyHint": True},
        tags={"meta"},
    )
    async def health_check() -> dict[str, Any]:
        """Check server health and version."""
        return {
            "status": "ok",
            "server": "linkedin-mcp-custom",
            "version": __version__,
            "message": "Server is running. Use get_saved_jobs to start.",
        }

    @mcp.tool(
        title="Get Saved Jobs",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "scraping"},
    )
    async def get_saved_jobs(ctx: Context) -> dict[str, Any]:
        """
        Get saved jobs from LinkedIn's /jobs-tracker/ page.

        Returns list of saved job IDs and raw text from the tracker page.
        Each job ID can be passed to further analysis.
        """
        await ctx.info("Fetching saved jobs from LinkedIn...")
        return {
            "status": "not_implemented",
            "message": "Scraper not yet implemented. Coming in Fáze 2.",
            "url": "https://www.linkedin.com/jobs-tracker/",
        }

    @mcp.tool(
        title="Analyze Saved Jobs",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "analysis"},
    )
    async def analyze_saved_jobs(ctx: Context) -> dict[str, Any]:
        """Full pipeline: scrape saved jobs → EROI → KB write."""
        await ctx.info("Analyze pipeline not yet implemented...")
        return {
            "status": "not_implemented",
            "message": "Analysis pipeline not yet implemented. Coming in Fáze 4.",
        }

    @mcp.tool(
        title="Close Session",
        annotations={"readOnlyHint": True},
        tags={"meta"},
    )
    async def close_session_tool() -> dict[str, Any]:
        """Close the browser session and cleanup resources."""
        await close_session()
        return {"status": "ok", "message": "Browser session closed"}

    return mcp
