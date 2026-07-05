# linkedin-mcp-custom

LinkedIn saved jobs analysis MCP server with EROI scoring and KB write-back.

Built from the ground up — inspired by [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) but focused only on saved jobs scraping, EROI analysis, and automated reporting.

## Architecture

```
MCP Client (Claude Code)
    │
    ▼
linkedin-mcp-custom (FastMCP server)
    │
    ├── core/       Browser management (Patchright) + auth
    ├── scraping/   LinkedInExtractor — navigate, innerText, noise strip
    ├── tools/      MCP tool implementations
    └── analysis/   EROI scoring engine + KB writer
```

## Quick start

```bash
# 1. Login to LinkedIn (first time only)
uv run python -m linkedin_mcp_custom --login

# 2. Check session status
uv run python -m linkedin_mcp_custom --status

# 3. Start MCP server
uv run python -m linkedin_mcp_custom
```

## Dependencies

- **fastmcp** — MCP server framework
- **patchright** — LinkedIn anti-detection browser automation (Playwright fork)
- **python-dotenv** — environment configuration

## Dev

```bash
uv sync              # Install dependencies
uv run ruff check .  # Lint
uv run ruff format . # Format
```

## Project state

See `ai_state.json` for current build phase and todo list.
