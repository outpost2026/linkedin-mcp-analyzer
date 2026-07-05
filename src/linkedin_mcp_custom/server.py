"""LinkedIn MCP Custom Server — FastMCP entry point."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_custom import __version__
from linkedin_mcp_custom.core import close_session
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
        return {
            "status": "ok",
            "server": "linkedin-mcp-analyzer",
            "version": __version__,
            "message": "Server is running. Use get_saved_jobs to start.",
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
