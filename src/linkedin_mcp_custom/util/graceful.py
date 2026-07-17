"""Graceful degradation — fast-path no-op responses for MCP.

Pattern: obscura fast_path_response() (crates/obscura-cdp/src/server.rs)
Returns valid empty/no-op responses instead of errors when a method
is not implemented, so MCP clients never crash on unknown features.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Standard no-op responses for optional MCP capabilities.
# FastMCP provides these by default, but we keep explicit overrides
# to guarantee graceful behavior even if SDK defaults change.
NOOP_RESPONSES: dict[str, dict[str, Any]] = {
    "prompts/list": {"prompts": []},
    "resources/list": {"resources": []},
    "resources/templates/list": {"resourceTemplates": []},
    "sampling/createMessage": {"role": "assistant", "content": {"type": "text", "text": ""}},
}


def noop_for(method: str) -> dict[str, Any] | None:
    """Return a no-op response for *method*, or None if unknown."""
    result = NOOP_RESPONSES.get(method)
    if result is not None:
        logger.debug("No-op response for %r", method)
    return result


def safe_tool_response(tool_name: str, result: Any) -> dict[str, Any]:
    """Wrap a tool's return value into a well-formed MCP response.

    Ensures every tool response has at least ``{"status": ..., "tool": ...}``
    so clients never see an unformatted exception.
    """
    if isinstance(result, dict):
        result.setdefault("tool", tool_name)
        result.setdefault("status", "ok")
        return result
    return {"status": "ok", "tool": tool_name, "data": result}
