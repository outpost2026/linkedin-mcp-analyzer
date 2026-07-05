# linkedin-mcp-analyzer

MCP server for automated LinkedIn saved jobs analysis with EROI scoring and KB write-back.

## Architecture

```
LinkedIn (saved jobs) → Patchright browser → Scraper → EROI scorer → KB writer
                         6 dimensions: domain 35%, tech 25%, role 20%,
                         growth 10%, formal 5%, location 5%
                         → agregovany_report.md + metadata_stacku.json + git commit
```

## Setup

```bash
uv sync
linkedin-mcp --login   # one-time LinkedIn auth
linkedin-mcp --status  # verify session
```

## Usage

```bash
# Start MCP server
linkedin-mcp

# Or via MCP client
uv run python -m linkedin_mcp_custom
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `get_saved_jobs` | List saved jobs from LinkedIn tracker |
| `get_job_details` | Scrape full posting for a job ID |
| `analyze_saved_jobs` | Full pipeline: scrape → EROI → KB write-back |

## EROI Scoring

### Dimensions

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Domain | 35% | Industrial automation vs adjacent vs noise |
| Tech | 25% | Skill overlap (content-aware match ratio × coverage) |
| Role | 20% | Engineering role vs "fake engineer" (service/sales) |
| Growth | 10% | Strategic employer (Siemens, Google…) vs growth vs other |
| Formal | 5% | Degree requirements with flexibility detection |
| Location | 5% | Remote/hybrid/CZ vs distant/office-only |

### Thresholds

| Score | Verdict |
|-------|---------|
| ≥65 | SLEDOVAT |
| 50–64 | MEDIUM |
| 40–49 | HRANICNI |
| <40 | NESLEDOVAT |

### Special patterns

- **Fake engineer**: title says "Engineer" but content is service/sales
- **Positioning match**: strong role match compensates for domain gap
- **Degree flexibility**: "equivalent practical experience" adds ~5%
- **Electronics manufacturing**: SMT/PCBA keywords cap domain score

## Tests

```bash
uv run python tests/test_eroi_regression.py   # 6 regression tests
uv run python tests/test_kb_writer.py          # 4 KB writer tests
```

## Phases

| Phase | What | Tag |
|-------|------|-----|
| 0 | Project scaffold | v0.1.0 |
| 1 | Browser + auth (Patchright) | — |
| 2 | Scraping engine (LinkedInExtractor) | — |
| 3 | MCP tools (get_saved_jobs, analyze…) | v0.2.0 |
| 4 | EROI engine (6 scorers) | v0.3.0 |
| 5 | KB writer (report + metadata + git commit) | v0.4.0 |
| 6 | DevOps (ruff, pre-commit, README) | v0.5.0 |
