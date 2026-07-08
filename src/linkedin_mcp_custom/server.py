"""LinkedIn MCP Custom Server — FastMCP entry point."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from linkedin_mcp_custom import __version__
from linkedin_mcp_custom.core import (
    check_session_status,
    close_session,
    get_page,
    get_session_age,
)
from linkedin_mcp_custom.tools.job import register_job_tools

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with all tools."""
    mcp = FastMCP(
        "linkedin-mcp-analyzer",
        version=__version__,
        instructions=(
            "Agentic LinkedIn saved jobs analysis server. "
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
        session_age = get_session_age()
        result: dict[str, Any] = {
            "status": "ok",
            "server": "linkedin-mcp-analyzer",
            "version": __version__,
            "session_age_hours": session_age,
            "message": "Server is running. Use get_saved_jobs to start.",
        }
        if session_age is not None and session_age > 24:
            result["warning"] = f"Session age {session_age}h exceeds 24h, re-login recommended"
        return result

    @mcp.tool(
        title="Check Session",
        annotations={"readOnlyHint": True},
        tags={"auth", "meta"},
    )
    async def check_session() -> dict[str, Any]:
        """Check LinkedIn session status with detailed diagnostics.

        Detects expired sessions, checkpoint/challenge pages,
        and rate-limiting before they cause tool failures.
        """
        try:
            page = await get_page()
            result = await check_session_status(page)
            return result
        except Exception as e:
            return {
                "status": "error",
                "detail": f"Session check failed: {e}",
            }

    # Register all job tools from tools/job.py
    register_job_tools(mcp)

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
