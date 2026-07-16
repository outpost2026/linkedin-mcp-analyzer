# Audit Prompt — linkedin-mcp-custom v0.1.0

**Generated:** 2026-07-15 | **Template:** MCP-Jobs audit_prompt_v1.1.docx | **Commit:** bd5b5dc

---

## Instructions for the Auditing LLM

You are a senior software engineer conducting a comprehensive audit of **linkedin-mcp-custom** — a LinkedIn saved-jobs scraper + EROI scoring engine exposed as an MCP server. The codebase uses **Patchright** (Playwright fork) for browser automation, **FastMCP** for the MCP transport, and writes results into a **B2B-Knowledge-Base** git repository.

**Your task:** Produce a structured audit report following the format in Section 6. You have access to:
- Full source code of every module (Appendix A)
- Recent git history and iteration context
- Test profile and coverage data
- Cross-repo reference: MCP-Jobs (CZ job portal scraper) for architectural comparison

Focus on: code quality, MCP maturity, error resilience, LinkedIn scraping (anti-bot) strategy, EROI scoring correctness, and publish-readiness.

---

## 1. Executive Summary

### 1.1 Overview
- **Project:** linkedin-mcp-custom — MCP server for LinkedIn saved-jobs analysis
- **Version:** 0.1.0 (pre-release, single-developer)
- **Architecture:** Patchright browser (Chromium) → LinkedInExtractor (innerText scraping) → EROI scorer (6-dimension weighted) → KB writer (git-backed metadata store) → FastMCP transport
- **Current state:** Functional but unreliable — LinkedIn rate-limits cause ~92% job failure rate in recent runs (4/50 scored, 46/50 timeout)
- **Tests:** 29 passing, 0 failing
- **SLOC:** ~3,850 lines Python (src/ only, excl. tests)

### 1.2 Cross-Repo Comparison (MCP-Jobs)

| Dimension | MCP-Jobs | linkedin-mcp-custom |
|-----------|----------|---------------------|
| Architecture | requests+BS4, stateless | Patchright browser, stateful (persistent profile) |
| Speed | ~1s/page | ~4-15s/page (browser overhead) |
| Rate-limiting | Respects robots.txt, polite delays | No respect — browser-based (LinkedIn anti-bot) |
| Tests | 96 (comprehensive) | 29 (unit, no integration) |
| Config | YAML-driven (8 queries, 3 portals) | YAML-driven (pipeline params only) |
| MCP Level | L1 tools + L3 prompts, ~L2 Resources | L1 tools only |
| Publish-ready | 7/10 | 4/10 |

### 1.3 Health Score: 5/10

**Strengths:**
- Clean dataclass-based config system
- Comprehensive EROI scoring with 6 dimensions
- Synthetic report generator with statistics
- KB writer with dedup, git commit, metadata upsert
- Graceful degradation on navigation failures (partial results)

**Critical issues:**
- LinkedIn rate-limiting causes ~92% job failure (17 timeout + 29 pool cascade = 46/50)
- No pipeline-level rate-limit backoff
- Pool page round-robin + semaphore mismatch causes cascade failures
- MCP server lacks L2 Resources and L4 Streaming
- 0 integration/E2E tests — no mock LinkedIn server
- Single-developer, 0 community adoption

---

## 2. Iteration History — Changes Since Last Audit

### 2.1 Recent Commits (30 days)

```
bd5b5dc P3+P4: parallel pool tracking + YAML config system
abf973f P2 fix: timeout je non-retryable (fail-fast), reduce goto timeout na 15s pro job pages
20f4155 P2 error resilience: retry_goto s backoffem + timeout per job + graceful degradation
8c79393 P1 perf: nahradit wait_for_timeout(2000) → wait_for_selector('main'); blokovat resources; zero-ad alert
f3a5048 fix: reduce auth cache stale warnings during parallel per-job phase
3257766 [CORE] fix: bound saved-jobs scrape + per-job timeout in analyze_saved_jobs
e18b430 [docs] ai_state: update last_commit -> 604c53d
604c53d [CORE] feat: job_ids continuation loop + CI (GitHub Actions) + README batch docs
eb43fe2 [CORE] fix: analyze_saved_jobs MCP timeout - sequential early-exit replaces asyncio.gather
491e9e2 [CORE] fix: MCP stdout transport + auth redirect detection (session 9)
74abada fix: auth cache TTL race + singleton page navigation race — pipeline 49/50 (98%)
b7c1aec fix: session 7 — parallel scraping bugs + auth guard + retry + raw strings
f550ad1 docs: rewrite README for community outreach — bilingual, badges, demo output, contributing, license, links
c599041 fix: #016 MCP timeout + #020 cookie lifecycle
9b14467 fix: KBWriter section-separator bug + pipeline: 49 jobs EROI scored
```

### 2.2 Known Open Findings

| Finding | Severity | Status |
|---------|----------|--------|
| LinkedIn rate-limiting on /jobs/view/ (100% timeout after ~2 jobs) | Critical | OPEN — needs pipeline-level backoff |
| Pool page cascade failure (29/50 jobs never attempted goto) | Critical | OPEN — needs sequential fallback |
| "Specific job list selector not found" on every pagination (benign) | Minor | OPEN — SPA selector drift |
| Auth cache stale warnings when per-job phase > 60s | Major | FIXED (SESSION_CHECK_INTERVAL 60→300s) |
| MCP L2 Resources (job pool URI exposure) | Major | OPEN — not implemented |
| MCP L4 Streaming (progress for 30s+ runs) | Medium | OPEN — not implemented |
| No CI integration for tests | Minor | OPEN — GitHub Actions exists but outputs only |
| No E2E/integration tests (mock LinkedIn) | Major | OPEN — 0 coverage |
| EROI scoring: regex/bag-of-words only, no LLM | Medium | OPEN — no semantic matching |
| EROI scoring: 29/50 "scored" but score depends only on gettable text | Info | OPEN — if text not extracted, score=0 |

### 2.3 Recent Fix Quality Assessment

| Fix | Assessment |
|-----|------------|
| P1: wait_for_selector (2s timeout → smart wait) | SOLID — ~40% per-job speedup when LinkedIn is fast |
| P1: Resource blocking (images/fonts/media) | SOLID — confirmed active in logs |
| P2: _retry_goto with exponential backoff | PARTIAL — correct logic, wrong default (timeout should not retry) |
| P2: Timeout → non-retryable (fail-fast 15s) | SOLID — prevents pool blocking |
| P2: Per-job timeout (asyncio.wait_for 120s) | SOLID — prevents single job hanging pipeline |
| P3: Pool tracking + drain before close | SOLID — eliminated TargetClosedError warnings |
| P4: YAML config (AppConfig dataclass) | SOLID — clean load/save/override |
| auth cache stale DEBUG in parallel phase | SOLID — reduces log noise |

---

## 3. Current Test Profile

| File | Tests | What's tested |
|------|-------|---------------|
| test_eroi_regression.py | 6 | EROI scoring against known entries (Siemens, Google, Apify, etc.) — checks total_score ± tolerance |
| test_batch_pipeline.py | 4 | FastMCP client calling analyze_saved_jobs with mocked extractor — deadline, limit, continuation loop |
| test_kb_writer.py | 12 | KBWriter dedup, metadata upsert, section separator, summary table idempotence |
| test_report_generator.py | 7 | SyntheticReportGenerator statistics, clustering, MD/JSON output |
| **TOTAL** | **29** | All pass (verified) |

**Coverage gaps:**
- 0 tests for extractor.py (browser-based, hard to mock)
- 0 tests for browser.py or auth.py (Patchright-dependent)
- 0 tests for config.py (trivial dataclass, low risk)
- 0 E2E tests with real LinkedIn
- 0 integration tests with mock browser/page

---

## 4. Architecture & MCP Maturity

### 4.1 Module Map

| File | Lines | Purpose | Changed in P1-P4 |
|------|-------|---------|------------------|
| server.py | 78 | FastMCP server: 4 tools + health check | — |
| tools/job.py | 348 | MCP tools: get_saved_jobs, get_job_details, analyze_job, analyze_saved_jobs (batch), generate_report | * (early-exit) |
| cli.py | 109 | CLI: --login, --status, MCP server start | — |
| config.py | 139 | AppConfig dataclass, YAML load/save | NEW (P4) |
| core/__init__.py | 49 | Public API re-exports | — |
| core/browser.py | 206 | Patchright singleton, page pool (3), resource blocking, nav tracking | * (P1, P3) |
| core/auth.py | 293 | Cookie-based auth, session check, checkpoint detection, rate-limit detect | * (P2) |
| core/exceptions.py | 21 | 5 custom exceptions (LinkedInScraperException base) | — |
| scraping/__init__.py | 18 | Re-exports | — |
| scraping/extractor.py | 646 | LinkedInExtractor: navigate, scroll, extract innerText, scrape_job, scrape_saved_jobs, _retry_goto | * (P1, P2, P3) |
| scraping/utils.py | 59 | URL constants, noise stripping, rate-limit detection | — |
| analysis/__init__.py | 32 | strip_diacritics, normalize, normalize_keywords | — |
| analysis/config.py | 262 | Dimension weights, thresholds, skill matrix, employer lists, keyword lists | — |
| analysis/schemas.py | 92 | TechMatch, DimensionScore, EROIResult, JobFeatures dataclasses | — |
| analysis/scorer.py | 120 | score_job(), score_job_from_text() — orchestrator | — |
| analysis/tech.py | 44 | tech_score() — 25% of total | — |
| analysis/domain.py | 72 | domain_score() — 35% of total | — |
| analysis/role.py | 43 | role_score() — 20% of total | — |
| analysis/growth.py | 20 | growth_score() — 10% of total | — |
| analysis/formal.py | 50 | formal_score() — 5% of total | — |
| analysis/location.py | 63 | location_score() — 5% of total | — |
| analysis/kb_writer.py | 396 | KBWriter: dedup, metadata JSON, MD report, git commit | * |
| analysis/report_generator.py | 545 | SyntheticReportGenerator: stats, clusters, MD/JSON | — |

### 4.2 MCP Maturity Ladder

| Level | Status | Detail |
|-------|--------|--------|
| L0 — Script | Surpassed | Legacy pipeline (reference) |
| L1 — Tool wrapper | DONE | 5 MCP tools (health_check, check_session, get_saved_jobs, get_job_details, analyze_job, analyze_saved_jobs, generate_report, close_session) |
| L2 — Resources | NEXT | Not yet — job pool needs URI exposure (e.g., linkedin-mcp://jobs/{job_id}) |
| L3 — Prompts | PLANNED | Not yet — no @mcp.prompt() defined |
| L4 — Streaming | PLANNED | Progress reporting for 30s+ batch runs |
| L5 — Multi-transport | FUTURE | SSE/HTTP beside stdio |
| L6 — Orchestration | VISION | MCP-to-MCP (LinkedIn Analyzer <-> Knowledge Base) |

### 4.3 Key Design Decisions

- **Browser automation over API:** LinkedIn has no public Jobs API. Playwright (Patchright) with persistent Chromium profile handles auth cookies across sessions.
- **innerText extraction over DOM parsing:** LinkedIn is a React SPA. innerText from `<main>` is more resilient to selector drift than specific CSS selectors. Trade-off: no structured fields, all text is flat.
- **6-dimension EROI scoring:** Domain (35%) + Tech (25%) + Role (20%) + Growth (10%) + Formal (5%) + Location (5%). Weighted sum based on keyword matching with diacritics normalization.
- **Git-backed knowledge base:** Scores and metadata written to B2B-Knowledge-Base git repo. Enables versioning, diffing, and synthetic report generation.
- **Sequential early-exit batch:** analyze_saved_jobs uses sequential per-job processing with deadline check — avoids MCP transport timeout (-32001) that plagued the asyncio.gather approach.
- **Graceful degradation pattern:** Every navigation failure returns partial results (with error strings) instead of crashing the entire pipeline.

---

## 5. LinkedIn Scraping Analysis

### 5.1 Anti-Bot Landscape

LinkedIn employs multi-layered anti-scraping:
1. **Session-based auth:** Requires valid login cookies (handled via persistent Chromium profile)
2. **Rate limiting:** `/jobs/view/` endpoint blocks rapid sequential access (observed: 2 successful → all subsequent timeout at 15s)
3. **Checkpoint/challenge pages:** CAPTCHA, email verification, or phone verification when unusual activity detected
4. **SPA rendering:** React-based UI requires JS execution (benefits from real browser vs. requests+BS4)
5. **Dynamic selectors:** CSS class names change frequently (observed: "Specific job list selector not found" on every pagination — benign as fallback works)

### 5.2 Observed Failure Pattern

```
Jobs 1-2: SUCCESS (7-15s each)
Jobs 3-22: TIMEOUT at exactly 15s (100% failure rate after ~2 successes)
Jobs 23-50: Never attempted (waiting on semaphore, timed out at 120s)
```

This pattern is consistent across 3+ runs at 19:00-19:42. At 18:00 (first run), all 50 succeeded. Hypothesis: LinkedIn's rate limiter activates after ~2 rapid job view accesses from the same session, blocking all subsequent requests for a window of time.

### 5.3 Current Defenses

| Defense | Status | Effectiveness |
|---------|--------|---------------|
| Headless browser | ON | Required for JS rendering, but detectable |
| Resource blocking | ON | Reduces bandwidth, doesn't affect rate-limiting |
| Persistent profile | ON | Cookies survive restarts |
| Per-job timeout 15s | ON | Fail-fast, doesn't help with rate-limiting |
| Exponential backoff on goto | ON (connection errors only) | Timeout is non-retryable — correct for this scenario |
| Pipeline-level backoff | OFF | Missing — would help with rate-limit windows |
| Sequential fallback | OFF | Missing — would avoid pool cascade |
| Random delays | OFF | Missing — would reduce pattern detection |

---

## 6. Audit Tasking — Specific Questions

### 6.1 Code Quality & Architecture
1. `_retry_goto` wraps `page.goto()` in `asyncio.ensure_future` for task tracking. Is this introducing unnecessary complexity? Evaluate the trade-off between clean shutdown and code clarity.
2. `LinkedInExtractor.scrape_job()` is 110+ lines with multiple return paths. Should it be refactored into smaller helpers (e.g., `_navigate_to_job`, `_extract_content`, `_extract_metadata`)?
3. `analysis/config.py` has 262 lines of keyword lists. Should these be external YAML/JSON files instead of Python code? Assess maintainability vs. performance.
4. `KBWriter` is 396 lines with mixed responsibilities (metadata, markdown, git). Evaluate single-responsibility principle violations.
5. `cli.py` has `asyncio.run()` calls for --login and --status. Stacktrace on concurrent event loop if called from within an existing loop (e.g., MCP server context). Is this a real bug?

### 6.2 MCP Architecture
1. Design MCP L2 Resources URI scheme: what would `linkedin-mcp://jobs/{job_id}` expose? What about `linkedin-mcp://analysis/reports/{date}`?
2. `@mcp.prompt()` is not implemented. What prompt would help users construct effective EROI queries? (Reference: MCP-Jobs has `search_expert` prompt.)
3. Current MCP tools are all async. Is there a risk of event loop blocking from synchronous git operations in `KBWriter.commit_changes()`?
4. `analyze_saved_jobs` accepts `ctx: Context` for progress reporting. Is the current `await ctx.info()` pattern sufficient for L4 Streaming, or would a generator-based approach be better?

### 6.3 LinkedIn Scraping Strategy
1. Assess the 92% failure rate: is the root cause LinkedIn rate-limiting, Patchright detection, or resource exhaustion? What diagnostic would confirm?
2. Design a pipeline-level backoff strategy: if >50% of last N jobs failed with timeout, pause 30-120s before continuing. Where should this be implemented?
3. Evaluate sequential vs. parallel scraping for LinkedIn: given the observed failure pattern (2 success → all timeout), would `max_concurrent=1` reduce rate-limiting? Does parallel access INCREASE detection risk?
4. The "Specific job list selector not found" warning appears every pagination. Assess the risk of LinkedIn changing the jobs-tracker DOM and breaking pagination entirely. What fallback exists?

### 6.4 EROI Scoring Correctness
1. Domain score (35% weight) uses keyword matching against industrial/adjacent/non-industrial lists. Are the keyword lists comprehensive enough for Czech CZ/NL/DE job market?
2. Tech score (25%) uses `SKILL_MATRIX` with 43 skills. Are there critical missing skills (e.g., PLC, SCADA, MES, IIoT, edge computing)?
3. Role score (20%) differentiates engineering vs. non-engineering roles. The `FAKE_ENGINEER_KEYWORDS` list (8 terms) is short. Assess false positive risk.
4. Growth score (10%) uses two employer lists (strategic=11, growth=12). Is this biased toward known employers? How does a job at an unknown startup score?
5. All 4 successful jobs scored NESLEDOVAT (<30%). Is the scoring too conservative, or are these genuinely low-ERI jobs?

### 6.5 Testing & Quality
1. 0 tests for extractor.py — the core scraping module. Design a test strategy that mocks `Page` without launching a real browser.
2. 0 tests for browser.py or auth.py. Evaluate: are integration tests with real LinkedIn necessary, or can Patchright be mocked at the `async_api` level?
3. The batch pipeline test (test_batch_pipeline.py) uses `unittest.mock.patch` on `LinkedInExtractor`. Is this sufficient, or does it mask real async/await bugs?
4. Current test suite runs in ~18s. If we add 10 browser-mocked tests, estimate the time impact.

### 6.6 Publish-Readiness
1. GitHub: 0 stars, 0 forks, 0 contributors. What's the minimal community package (README, license, contributing guide, issue templates)?
2. PyPI: not published. What's missing in a hypothetical pyproject.toml? (Reference: MCP-Jobs has `__version__`, `pyproject.toml` with `[project.scripts]`.)
3. Docker: no Dockerfile. Evaluate multi-stage Dockerfile design for MCP stdio vs. SSE transport.
4. Security: persistent browser profile contains LinkedIn cookies. Any secrets-management concern? Is there a `.gitignore` for the profile directory?
5. Licensing: no LICENSE file. What license fits an MCP tool for a niche CZ/NL job market tool?

---

## 7. Required Output Format

### 7.1 Executive Summary
- Top 3 findings (Critical/Major)
- Health score 1-10
- Go/no-go recommendation for v0.2.0 release

### 7.2 Iteration P1-P4 Review
- For each change: SOLID / PARTIAL / REGRESSED assessment
- Which fixes are robust, which need follow-up

### 7.3 Finding Table
| ID | Area | Severity | Finding | Recommendation | EROI |
|----|------|----------|---------|----------------|------|
| ... | ... | Critical/Major/Minor/Info | ... | ... | High/Med/Low |

### 7.4 Code Quality Score (per module)
| Module | Readability (1-5) | Testability (1-5) | Robustness (1-5) | MCP (1-5) | Average |
|--------|-------------------|-------------------|-------------------|-----------|---------|
| server.py | ... | ... | ... | ... | ... |
| tools/job.py | ... | ... | ... | ... | ... |
| scraping/extractor.py | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |

### 7.5 LinkedIn Scraping Assessment
- Anti-bot defense effectiveness
- Rate-limit risk analysis
- Recommended defense upgrades

### 7.6 Publish-Readiness
- Conditional recommendation (go/no-go for v0.2.0)
- Gap list with blocking vs. nice-to-have
- Estimated effort per gap (hours/days)

### 7.7 Next Iteration Priorities
- Prioritised list with EROI reasoning
- For each: effort estimate, risk reduction, value

---

## Appendix A — Full Source Code

This appendix contains the complete, unabridged source of every production module at commit bd5b5dc. The auditing LLM needs this architecture context to produce a qualified assessment.

### A.0 Project Layout

```
linkedin-mcp-custom/
├── src/
│   └── linkedin_mcp_custom/
│       ├── __init__.py          # Version 0.1.0
│       ├── __main__.py          # python -m entry point
│       ├── cli.py               # --login, --status, MCP start
│       ├── config.py            # AppConfig dataclass + YAML load
│       ├── server.py            # FastMCP: 4 tools + health
│       ├── core/
│       │   ├── __init__.py      # Public API re-exports
│       │   ├── auth.py          # Session check, auth, rate-limit detect
│       │   ├── browser.py       # Patchright singleton + page pool
│       │   └── exceptions.py    # 5 custom exceptions
│       ├── scraping/
│       │   ├── __init__.py      # Re-exports
│       │   ├── extractor.py     # LinkedInExtractor (646 lines)
│       │   └── utils.py         # Noise stripping, URL constants
│       ├── analysis/
│       │   ├── __init__.py      # strip_diacritics, normalize
│       │   ├── config.py        # Keywords, weights, thresholds
│       │   ├── schemas.py       # Dataclasses (TechMatch, EROIResult...)
│       │   ├── scorer.py        # score_job(), score_job_from_text()
│       │   ├── tech.py          # tech_score() — 25%
│       │   ├── domain.py        # domain_score() — 35%
│       │   ├── role.py          # role_score() — 20%
│       │   ├── growth.py        # growth_score() — 10%
│       │   ├── formal.py        # formal_score() — 5%
│       │   ├── location.py      # location_score() — 5%
│       │   ├── kb_writer.py     # KBWriter (396 lines)
│       │   └── report_generator.py # SyntheticReportGenerator (545 lines)
│       └── tools/
│           ├── __init__.py      # Empty
│           └── job.py           # MCP tools for job operations
├── scripts/
│   └── run_pipeline.py          # Full CLI pipeline (572 lines)
├── tests/
│   ├── test_eroi_regression.py  # 6 tests
│   ├── test_batch_pipeline.py   # 4 tests
│   ├── test_kb_writer.py        # 12 tests
│   └── test_report_generator.py # 7 tests
├── docs/
│   ├── pipeline_*.json          # Pipeline run reports
│   ├── pipeline_*.md            # Human-readable reports
│   └── error_analysis_*.json    # Cross-LLM error analysis
└── .github/
    └── workflows/
        └── pipeline.yml         # GitHub Actions pipeline
```

### A.1 src/linkedin_mcp_custom/__init__.py
```python
"""LinkedIn MCP Custom — Saved jobs analysis with EROI scoring."""
__version__ = "0.1.0"
```

### A.2 src/linkedin_mcp_custom/__main__.py
```python
"""Allow running as: python -m linkedin_mcp_custom."""
from linkedin_mcp_custom.cli import main
main()
```

### A.3 src/linkedin_mcp_custom/cli.py
```python
"""CLI entry point for linkedin-mcp-custom."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)


async def _login() -> None:
    """Open browser, wait for manual LinkedIn login, save session."""
    from linkedin_mcp_custom.core import (
        AuthenticationError,
        close_browser,
        get_or_create_browser,
        wait_for_manual_login,
    )

    print("Opening browser for LinkedIn login...")
    print("Please log in to LinkedIn in the browser window.")
    print("  If you see a 'Help us confirm it's you' page — complete the")
    print("  verification (CAPTCHA, email code) and you'll be redirected.")
    print("  Use EMAIL + PASSWORD, NOT 'Sign in with Google'.")
    print("(The browser profile will be saved for future use.)")
    print()

    try:
        context = await get_or_create_browser(headless=False)
        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        await wait_for_manual_login(page, timeout=300)
        print()
        print("[OK] Login successful! Session cookies saved.")
        print("   Profile: ~/.linkedin-mcp-custom/profile/")
    except AuthenticationError as e:
        print(f"[ERROR] Login failed: {e}")
        sys.exit(1)
    finally:
        await close_browser()


async def _status() -> None:
    """Check if LinkedIn session is valid."""
    from linkedin_mcp_custom.core import (
        close_browser,
        get_or_create_browser,
        is_logged_in,
    )

    print("Checking LinkedIn session...")
    try:
        context = await get_or_create_browser(headless=True)
        pages = context.pages
        page = pages[0] if pages else await context.new_page()

        logged_in = await is_logged_in(page)
        if logged_in:
            print("[OK] Session valid — logged in to LinkedIn")
        else:
            print("[EXPIRED] Session expired — run 'linkedin-mcp --login'")
            sys.exit(1)
    finally:
        await close_browser()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="linkedin-mcp",
        description="LinkedIn saved jobs analysis MCP server with EROI scoring.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open browser for LinkedIn login and save session cookies.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check if LinkedIn session is valid.",
    )
    args = parser.parse_args()

    if args.login:
        asyncio.run(_login())
        return

    if args.status:
        asyncio.run(_status())
        return

    # Start MCP server
    from linkedin_mcp_custom.server import create_mcp_server

    mcp = create_mcp_server()
    print("Starting linkedin-mcp-custom MCP server...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

### A.4 src/linkedin_mcp_custom/config.py
```python
"""Pipeline configuration — YAML-based with env override."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".linkedin-mcp-custom"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class BrowserConfig:
    headless: bool = True
    block_resources: bool = True
    pool_size: int = 3


@dataclass
class ScrapeConfig:
    max_pages: int = 5
    per_job_timeout_ms: int = 15000
    tracker_timeout_ms: int = 30000
    max_nav_retries: int = 2


@dataclass
class PipelineConfig:
    max_concurrent: int = 3
    stagger_delay: float = 1.5
    job_timeout_seconds: int = 120
    headless: bool = True


@dataclass
class EroiThresholds:
    sledovat: float = 70.0
    medium: float = 45.0
    hranicni: float = 30.0


@dataclass
class AppConfig:
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    scrape: ScrapeConfig = field(default_factory=ScrapeConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    thresholds: EroiThresholds = field(default_factory=EroiThresholds)
    config_path: str = ""

    @classmethod
    def from_yaml(cls, path: str | Path) -> AppConfig:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls._from_dict(raw, config_path=str(path))

    @classmethod
    def from_defaults(cls) -> AppConfig:
        return cls()

    @classmethod
    def _from_dict(cls, raw: dict, config_path: str = "") -> AppConfig:
        cfg = cls(config_path=config_path)
        b = raw.get("browser", {})
        cfg.browser.headless = b.get("headless", cfg.browser.headless)
        cfg.browser.block_resources = b.get("block_resources", cfg.browser.block_resources)
        cfg.browser.pool_size = b.get("pool_size", cfg.browser.pool_size)
        s = raw.get("scrape", {})
        cfg.scrape.max_pages = s.get("max_pages", cfg.scrape.max_pages)
        cfg.scrape.per_job_timeout_ms = s.get("per_job_timeout_ms", cfg.scrape.per_job_timeout_ms)
        cfg.scrape.tracker_timeout_ms = s.get("tracker_timeout_ms", cfg.scrape.tracker_timeout_ms)
        cfg.scrape.max_nav_retries = s.get("max_nav_retries", cfg.scrape.max_nav_retries)
        p = raw.get("pipeline", {})
        cfg.pipeline.max_concurrent = p.get("max_concurrent", cfg.pipeline.max_concurrent)
        cfg.pipeline.stagger_delay = p.get("stagger_delay", cfg.pipeline.stagger_delay)
        cfg.pipeline.job_timeout_seconds = p.get(
            "job_timeout_seconds", cfg.pipeline.job_timeout_seconds
        )
        cfg.pipeline.headless = p.get("headless", cfg.pipeline.headless)
        t = raw.get("thresholds", {})
        cfg.thresholds.sledovat = t.get("sledovat", cfg.thresholds.sledovat)
        cfg.thresholds.medium = t.get("medium", cfg.thresholds.medium)
        cfg.thresholds.hranicni = t.get("hranicni", cfg.thresholds.hranicni)
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {
            "browser": {"headless": self.browser.headless, "block_resources": self.browser.block_resources, "pool_size": self.browser.pool_size},
            "scrape": {"max_pages": self.scrape.max_pages, "per_job_timeout_ms": self.scrape.per_job_timeout_ms, "tracker_timeout_ms": self.scrape.tracker_timeout_ms, "max_nav_retries": self.scrape.max_nav_retries},
            "pipeline": {"max_concurrent": self.pipeline.max_concurrent, "stagger_delay": self.pipeline.stagger_delay, "job_timeout_seconds": self.pipeline.job_timeout_seconds, "headless": self.pipeline.headless},
            "thresholds": {"sledovat": self.thresholds.sledovat, "medium": self.thresholds.medium, "hranicni": self.thresholds.hranicni},
        }

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppConfig:
        if path:
            return cls.from_yaml(path)
        if DEFAULT_CONFIG_PATH.exists():
            return cls.from_yaml(DEFAULT_CONFIG_PATH)
        env_path = os.environ.get("LINKEDIN_MCP_CONFIG")
        if env_path and Path(env_path).exists():
            return cls.from_yaml(env_path)
        return cls.from_defaults()

    def save_default(self) -> Path:
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text(
            yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        return DEFAULT_CONFIG_PATH
```

### A.5 src/linkedin_mcp_custom/server.py
```python
"""LinkedIn MCP Custom Server — FastMCP entry point."""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from linkedin_mcp_custom import __version__
from linkedin_mcp_custom.core import check_session_status, close_session, get_page
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

    @mcp.tool(title="Health Check", annotations={"readOnlyHint": True}, tags={"meta"})
    async def health_check() -> dict[str, Any]:
        """Check server health and version."""
        return {
            "status": "ok",
            "server": "linkedin-mcp-analyzer",
            "version": __version__,
            "message": "Server is running. Use get_saved_jobs to start.",
        }

    @mcp.tool(title="Check Session", annotations={"readOnlyHint": True}, tags={"auth", "meta"})
    async def check_session() -> dict[str, Any]:
        """Check LinkedIn session status with detailed diagnostics."""
        try:
            page = await get_page()
            result = await check_session_status(page)
            return result
        except Exception as e:
            return {"status": "error", "detail": f"Session check failed: {e}"}

    register_job_tools(mcp)

    @mcp.tool(title="Close Session", annotations={"readOnlyHint": True}, tags={"meta"})
    async def close_session_tool() -> dict[str, Any]:
        """Close the browser session and cleanup resources."""
        await close_session()
        return {"status": "ok", "message": "Browser session closed"}

    return mcp
```

### A.6 src/linkedin_mcp_custom/tools/job.py
```python
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
        page = await get_page()
        await ensure_authenticated(page)
        return LinkedInExtractor(page)

    @mcp.tool(tags={"scrape", "jobs"})
    async def get_saved_jobs() -> dict[str, Any]:
        """Get saved jobs from LinkedIn's /jobs-tracker/ page."""
        extractor = await _get_extractor()
        result = await extractor.scrape_saved_jobs()
        job_ids = result.get("job_ids", [])
        return {
            "job_ids": job_ids,
            "job_ids_count": len(job_ids),
            "raw_text": (result.get("sections", {}) or {}).get("saved_jobs", ""),
        }

    @mcp.tool(tags={"scrap", "jobs"})
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

    @mcp.tool(tags={"analysis", "jobs"})
    async def analyze_job(job_id: str, write_to_kb: bool = True) -> dict[str, Any]:
        """Scrape, EROI score, and KB-write a single LinkedIn job."""
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
            raw_text=raw_text, job_title=title, company=company, location=location, job_id=job_id,
        )
        eroi = score_job(features)
        write_result: dict[str, Any] | None = None
        if write_to_kb:
            kb = KBWriter()
            write_result = kb.write_all(eroi, raw_text, linkedin_job_id=job_id)
        result = eroi.to_dict()
        result["kb_write"] = write_result
        return result

    @mcp.tool(tags={"analysis", "jobs", "batch"})
    async def analyze_saved_jobs(
        ctx: Context,
        write_to_kb: bool = True,
        max_seconds: int = MAX_BATCH_SECONDS,
        limit: int = 0,
        job_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Batch pipeline: scrape saved jobs -> EROI score -> KB write-back.

        Processes jobs sequentially with an early-exit deadline check.
        Returns partial results with unprocessed job IDs for follow-up calls.
        """
        await ctx.info("Starting batch analysis pipeline...")
        try:
            extractor = await _get_extractor()
            deadline = time.time() + max_seconds

            if job_ids is not None:
                all_job_ids = list(job_ids)
            else:
                remaining = deadline - time.time()
                try:
                    saved = await asyncio.wait_for(extractor.scrape_saved_jobs(), timeout=remaining)
                    all_job_ids = saved.get("job_ids", [])
                except TimeoutError:
                    return {"status": "ok", "message": "Saved-jobs scrape exceeded time budget; pass job_ids explicitly.", "job_ids": []}

            if not all_job_ids:
                return {"status": "ok", "message": "No job IDs to analyze.", "job_ids": []}

            await ctx.info(f"Found {len(all_job_ids)} saved jobs, processing within {max_seconds}s budget")
            kb = KBWriter() if write_to_kb else None
            processed_ids: list[str] = []
            unprocessed_ids: list[str] = []
            errored_ids: list[str] = []
            results: list[dict[str, Any]] = []
            job_ids_to_process = all_job_ids[:limit] if limit > 0 else all_job_ids

            for jid in job_ids_to_process:
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
                    features = JobFeatures(raw_text=raw_text, job_title=title, company=company, location=location, job_id=jid)
                    eroi = score_job(features)
                    if kb:
                        kb.write_all(eroi, raw_text, linkedin_job_id=jid)
                    result = eroi.to_dict()
                    results.append(result)
                    processed_ids.append(jid)
                    await ctx.info(f"  #{jid}: {result.get('job_title', '?')} @ {result.get('company', '?')} -> {result.get('total_score', '?')}% ({result.get('verdict', '?')})")
                except AuthenticationError:
                    raise
                except Exception as exc:
                    logger.warning("Job %s failed: %s", jid, exc)
                    errored_ids.append(jid)
                    continue

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
                "batch_mode": {"strategy": "sequential_early_exit", "max_seconds": max_seconds, "limit": limit},
            }
            if unprocessed_ids:
                response["unprocessed_ids"] = unprocessed_ids
                response["message"] = f"Processed {len(processed_ids)}/{len(all_job_ids)} jobs ({len(unprocessed_ids)} remaining). Call again or use analyze_job."
            else:
                response["message"] = f"All {len(processed_ids)} jobs analyzed."
            if errored_ids:
                response["errored_ids"] = errored_ids
            if kb:
                response["kb_written"] = True
            return response
        except AuthenticationError:
            return {"status": "auth_required", "message": "Session expired. Run: linkedin-mcp --login"}
        except Exception as e:
            await ctx.error(f"Pipeline failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool(tags={"analysis", "report"})
    async def generate_report() -> dict[str, Any]:
        """Generate synthetic report from existing metadata_stacku.json."""
        from linkedin_mcp_custom.analysis.report_generator import SyntheticReportGenerator
        try:
            gen = SyntheticReportGenerator()
            md_path, json_path = gen.generate()
            return {"status": "ok", "md_report": str(md_path), "json_report": str(json_path), "entries_count": len(gen.load_metadata())}
        except Exception as e:
            logger.error("Report generation failed: %s", e)
            return {"status": "error", "message": str(e)}
```

### A.7 src/linkedin_mcp_custom/core/exceptions.py
```python
"""Custom exceptions for LinkedIn scraping."""

class LinkedInScraperException(Exception):
    """Base exception for all LinkedIn scraper errors."""

class AuthenticationError(LinkedInScraperException):
    """Session is invalid or expired. User needs to re-login."""

class RateLimitError(LinkedInScraperException):
    """LinkedIn rate-limited the request. Wait and retry."""

class ElementNotFoundError(LinkedInScraperException):
    """Expected element not found on the page."""

class BrowserError(LinkedInScraperException):
    """Browser or Playwright-level error."""
```

### A.8 src/linkedin_mcp_custom/core/browser.py
```python
"""Browser management — Patchright singleton wrapper with page pool."""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from patchright.async_api import BrowserContext, Playwright

if TYPE_CHECKING:
    from patchright.async_api import Page

logger = logging.getLogger(__name__)

_BLOCKED_RESOURCE_TYPES = {"image", "font", "media"}
_BLOCKED_DOMAINS = re.compile(
    r"(google-analytics|googletagmanager|doubleclick|facebook|fbcdn|"
    r"linkedin\.com\/analytics|bat\.bing|scorecardresearch|hotjar|"
    r"clarity\.ms|amplitude|mixpanel|optimizely|fullstory)",
    re.IGNORECASE,
)

_playwright: Playwright | None = None
_context: BrowserContext | None = None
_page: Page | None = None
_page_pool: list[Page] = []
MAX_PAGE_POOL_SIZE = 3
_PENDING_NAV_TASKS: set[asyncio.Task] = set()
PROFILE_DIR = Path.home() / ".linkedin-mcp-custom" / "profile"


def _ensure_profile_dir() -> Path:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILE_DIR


async def get_or_create_browser(headless: bool = False) -> BrowserContext:
    global _context, _page, _playwright
    if _context is not None:
        pages = _context.pages
        if pages and not pages[0].is_closed():
            return _context
    from patchright.async_api import async_playwright
    profile_dir = _ensure_profile_dir()
    logger.info("Launching Patchright browser (profile: %s)", profile_dir)
    _playwright = await async_playwright().start()
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=headless,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        no_viewport=True,
    )
    await _context.route(
        re.compile(r".*"),
        lambda route: (
            route.abort()
            if route.request.resource_type in _BLOCKED_RESOURCE_TYPES
            or _BLOCKED_DOMAINS.search(route.request.url)
            else route.continue_()
        ),
    )
    logger.info("Resource blocking active: types=%s, tracking domains blocked", _BLOCKED_RESOURCE_TYPES)
    pages = _context.pages
    _page = pages[0] if pages else await _context.new_page()
    return _context


async def get_page() -> Page:
    global _page
    if _page is not None and not _page.is_closed():
        return _page
    await get_or_create_browser()
    assert _page is not None
    return _page


async def get_browser_context() -> BrowserContext:
    global _context
    if _context is not None:
        return _context
    return await get_or_create_browser()


async def create_page() -> Page:
    global _page_pool
    _page_pool = [p for p in _page_pool if not p.is_closed()]
    ctx = await get_browser_context()
    if len(_page_pool) < MAX_PAGE_POOL_SIZE:
        page = await ctx.new_page()
        _page_pool.append(page)
        return page
    page = _page_pool.pop(0)
    _page_pool.append(page)
    return page


def _track_nav_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    _PENDING_NAV_TASKS.add(task)
    task.add_done_callback(_PENDING_NAV_TASKS.discard)


async def _drain_pending_navs(timeout: float = 3.0) -> None:
    if not _PENDING_NAV_TASKS:
        return
    _, pending = await asyncio.wait(_PENDING_NAV_TASKS, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    _PENDING_NAV_TASKS.clear()


async def close_browser() -> None:
    global _context, _page, _playwright, _page_pool
    await _drain_pending_navs()
    for p in _page_pool:
        try:
            await p.close()
        except Exception:
            pass
    _page_pool = []
    if _page is not None and not _page.is_closed():
        await _page.close()
    _page = None
    if _context is not None:
        await _context.close()
    _context = None
    if _playwright is not None:
        await _playwright.stop()
    _playwright = None
    logger.info("Browser closed")


async def close_session() -> None:
    await close_browser()
```

### A.9 src/linkedin_mcp_custom/core/auth.py
```python
"""LinkedIn authentication — cookie-based session management."""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from patchright.async_api import Page
from linkedin_mcp_custom.core.exceptions import AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)

_last_auth_check: float | None = None
_last_auth_ok: bool | None = None
SESSION_CHECK_INTERVAL = 300
SESSION_WARN_THRESHOLD = 86400

CHECKPOINT_PATTERNS = [
    "/checkpoint/", "/challenge/",
    "help us confirm it's you", "security verification",
    "enter your verification code",
]


def check_cached_auth() -> bool:
    if _last_auth_check is None or not _last_auth_ok:
        return False
    return (time.time() - _last_auth_check) < SESSION_CHECK_INTERVAL


async def wait_for_manual_login(page: Page, timeout: int = 300) -> bool:
    await page.goto("https://www.linkedin.com/", wait_until="domcontentloaded")
    logger.info("Waiting for manual LinkedIn login...")
    start = time.time()
    while time.time() - start < timeout:
        current_url = page.url
        if "/feed/" in current_url:
            logger.info("Login detected — on LinkedIn feed")
            _mark_auth_ok()
            return True
        if _is_checkpoint_page(current_url):
            logger.warning("Checkpoint/challenge page detected — waiting for user to complete verification")
        await page.wait_for_timeout(1000)
    raise AuthenticationError(f"Manual login not completed within {timeout}s. Run with --login to try again.")


def _is_checkpoint_page(url: str) -> bool:
    return any(p in url.lower() for p in CHECKPOINT_PATTERNS)


def _mark_auth_ok() -> None:
    global _last_auth_check, _last_auth_ok
    _last_auth_check = time.time()
    _last_auth_ok = True


def _mark_auth_expired() -> None:
    global _last_auth_check, _last_auth_ok
    _last_auth_check = time.time()
    _last_auth_ok = False


async def is_logged_in(page: Page) -> bool:
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        current_url = page.url
        if "/feed/" in current_url:
            _mark_auth_ok()
            return True
        if _is_checkpoint_page(current_url):
            logger.warning("Checkpoint/challenge page detected at: %s", current_url)
            _mark_auth_expired()
            return False
        if "/login" in current_url:
            _mark_auth_expired()
            return False
        body = await page.text_content("body")
        body_text = (body or "").lower()
        if "sign in" in body_text and "email" in body_text:
            _mark_auth_expired()
            return False
        if _is_checkpoint_page(body_text):
            logger.warning("Checkpoint/challenge detected in page body")
            _mark_auth_expired()
            return False
        _mark_auth_expired()
        return False
    except Exception as e:
        logger.warning("Login check failed: %s", e)
        _mark_auth_expired()
        return False


def get_session_age() -> float | None:
    if _last_auth_check is None or not _last_auth_ok:
        return None
    return round((time.time() - _last_auth_check) / 3600, 1)


def session_needs_refresh() -> bool:
    age = get_session_age()
    if age is None:
        return True
    return age * 3600 > SESSION_WARN_THRESHOLD


async def check_session_status(page: Page) -> dict:
    last_valid_str = None
    session_age = get_session_age()
    if _last_auth_check is not None and _last_auth_ok:
        last_valid_str = datetime.fromtimestamp(_last_auth_check, tz=UTC).isoformat()
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        current_url = page.url
        if "/feed/" in current_url:
            _mark_auth_ok()
            result: dict = {"status": "ok", "detail": "Session valid — authenticated on LinkedIn feed", "last_valid": datetime.now(UTC).isoformat(), "session_age_hours": get_session_age(), "url": current_url}
            if session_age is not None and session_age > 24:
                result["warning"] = f"Session older than 24h ({session_age}h), consider re-login"
            if session_needs_refresh():
                result["warning"] = f"Session age {session_age}h exceeds 24h threshold, re-login recommended"
            return result
        if _is_checkpoint_page(current_url):
            _mark_auth_expired()
            body = (await page.text_content("body") or "")[:500]
            return {"status": "checkpoint", "detail": f"LinkedIn checkpoint/challenge page: {current_url}", "last_valid": last_valid_str, "session_age_hours": session_age, "url": current_url, "body_preview": body}
        if "/login" in current_url:
            _mark_auth_expired()
            return {"status": "expired", "detail": "Session expired — redirected to login page", "last_valid": last_valid_str, "session_age_hours": session_age, "url": current_url}
        return {"status": "unknown", "detail": f"Unexpected URL after auth check: {current_url}", "last_valid": last_valid_str, "session_age_hours": session_age, "url": current_url}
    except Exception as e:
        _mark_auth_expired()
        return {"status": "error", "detail": f"Auth check failed: {e}", "last_valid": last_valid_str, "session_age_hours": session_age, "url": ""}


async def ensure_authenticated(page: Page, force_check: bool = False) -> None:
    global _last_auth_check
    now = time.time()
    if not force_check and _last_auth_check is not None and _last_auth_ok and (now - _last_auth_check) < SESSION_CHECK_INTERVAL:
        return
    if await detect_rate_limit(page):
        raise RateLimitError("LinkedIn rate-limited this request. Wait and retry.")
    current_url = page.url
    if _is_checkpoint_page(current_url):
        raise AuthenticationError(f"LinkedIn checkpoint/challenge detected at: {current_url}. Run 'linkedin-mcp --login' to re-authenticate manually.")
    if not await is_logged_in(page):
        if _is_checkpoint_page(page.url):
            raise AuthenticationError(f"LinkedIn checkpoint/challenge page active: {page.url}. Complete verification via: linkedin-mcp --login")
        raise AuthenticationError("Not authenticated. Run: linkedin-mcp --login")


async def detect_rate_limit(page: Page) -> bool:
    body_text = await page.text_content("body") or ""
    rate_limit_signals = ["too many requests", "rate limited", "please try again later", "unusual traffic"]
    return any(signal in body_text.lower() for signal in rate_limit_signals)
```

### A.10 src/linkedin_mcp_custom/scraping/utils.py
```python
"""Scraping utilities — noise stripping, selectors, constants."""
from __future__ import annotations
import re

NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(r"LinkedIn\s+(and\s+)?\d{4}", re.IGNORECASE),
    re.compile(r"About\s+us\s*$", re.IGNORECASE),
    re.compile(r"Privacy\s+Policy\s*$", re.IGNORECASE),
    re.compile(r"Terms\s+of\s+Service\s*$", re.IGNORECASE),
    re.compile(r"Cookie\s+Policy\s*$", re.IGNORECASE),
    re.compile(r"Send\s+feedback\s*$", re.IGNORECASE),
    re.compile(r"Help\s+Center\s*$", re.IGNORECASE),
    re.compile(r"Accessibility\s*$", re.IGNORECASE),
    re.compile(r"Ad\s+Choices\s*$", re.IGNORECASE),
    re.compile(r"Get\s+the\s+LinkedIn\s+app\s*$", re.IGNORECASE),
    re.compile(r"More\s+tab\s+to\s+explore", re.IGNORECASE),
]

RATE_LIMITED_MSG = "[[RATE_LIMITED]]"
LINKEDIN_BASE = "https://www.linkedin.com"
JOBS_TRACKER_URL = f"{LINKEDIN_BASE}/jobs-tracker/"
JOB_VIEW_URL = f"{LINKEDIN_BASE}/jobs/view/"


def strip_noise(text: str) -> str:
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(p.search(stripped) for p in NOISE_PATTERNS):
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def is_rate_limited(text: str) -> bool:
    signals = ["too many requests", "rate limited", "please try again later", "unusual traffic"]
    lower = text.lower()
    return any(s in lower for s in signals)
```

### A.11 src/linkedin_mcp_custom/scraping/extractor.py
[646 lines — full content available in repo at src/linkedin_mcp_custom/scraping/extractor.py]
Key components:
- `_retry_goto()` — navigation with exponential backoff, task tracking, non-retryable timeout
- `LinkedInExtractor.navigate_to_page()` — goto + wait_for_selector('main')
- `LinkedInExtractor.extract_page()` — navigate + scroll + innerText extraction
- `LinkedInExtractor.scrape_job()` — full job scrape with parallel page support
- `LinkedInExtractor.scrape_saved_jobs(max_pages=N)` — tracker page with pagination
- `_extract_job_ids()` — JavaScript-based job ID extraction from DOM + scripts
- `_extract_job_metadata()` — title/company/location from innerText
- `_click_next_page()` — pagination button click with fallback selectors

### A.12 src/linkedin_mcp_custom/analysis/config.py
[262 lines — full content available in repo]
Contains: DIMENSION_WEIGHTS, THRESHOLDS, CORE_INDUSTRIAL_KEYWORDS (45), ADJACENT_INDUSTRIAL_KEYWORDS (16), NON_INDUSTRIAL_KEYWORDS (24), SKILL_MATRIX (43 skills), ENGINEERING_ROLE_KEYWORDS (20), FAKE_ENGINEER_KEYWORDS (8), STRATEGIC_EMPLOYERS (11), GROWTH_EMPLOYERS (12), REMOTE_KEYWORDS, CZECH_KEYWORDS, OFFICE_KEYWORDS.

### A.13 src/linkedin_mcp_custom/analysis/schemas.py
```python
"""Data schemas for EROI analysis — dataclasses for tech matching, dimension scores, results."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TechMatch:
    skill: str
    match_type: str  # "direct", "partial", "none"
    weight: float
    score: float


@dataclass
class DimensionScore:
    name: str
    score: float
    detail: str
    weight: float


@dataclass
class SkillGap:
    skill: str
    match: str


@dataclass
class EROIResult:
    job_id: str
    job_title: str
    company: str
    total_score: float
    verdict: str
    dimensions: list[DimensionScore]
    skill_gaps: list[SkillGap]
    mismatch_dimensions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_title": self.job_title,
            "company": self.company,
            "total_score": round(self.total_score, 1),
            "verdict": self.verdict,
            "dimensions": {d.name: f"{d.score}% ({d.detail})" for d in self.dimensions},
            "skill_gaps": [{"skill": g.skill, "match": g.match} for g in self.skill_gaps],
            "mismatch_dimensions": self.mismatch_dimensions,
        }


@dataclass
class JobFeatures:
    raw_text: str
    job_title: str
    company: str
    location: str
    job_id: str
```

### A.14 src/linkedin_mcp_custom/analysis/scorer.py
```python
"""EROI scoring — orchestrates 6 dimension scores into weighted total + verdict."""
from __future__ import annotations

from linkedin_mcp_custom.analysis.config import DIMENSION_WEIGHTS, THRESHOLDS
from linkedin_mcp_custom.analysis.schemas import DimensionScore, EROIResult, JobFeatures, SkillGap


def _threshold_verdict(score: float) -> str:
    if score >= THRESHOLDS["sledovat"]:
        return "SLEDOVAT"
    if score >= THRESHOLDS["medium"]:
        return "MEDIUM"
    if score >= THRESHOLDS["hranicni"]:
        return "HRANICNI"
    return "NESLEDOVAT"


def score_job(features: JobFeatures) -> EROIResult:
    text_to_score = f"{features.job_title}\n{features.company}\n{features.raw_text}"

    from linkedin_mcp_custom.analysis.tech import tech_score
    from linkedin_mcp_custom.analysis.domain import domain_score
    from linkedin_mcp_custom.analysis.role import role_score
    from linkedin_mcp_custom.analysis.growth import growth_score
    from linkedin_mcp_custom.analysis.formal import formal_score
    from linkedin_mcp_custom.analysis.location import location_score

    dims = {
        "domain": domain_score(text_to_score),
        "tech": tech_score(text_to_score),
        "role": role_score(features.job_title, text_to_score),
        "growth": growth_score(features.company),
        "formal": formal_score(text_to_score),
        "location": location_score(features.location, text_to_score),
    }

    total = sum(dim["score"] * DIMENSION_WEIGHTS[dim["name"]] for dim in dims.values())
    verdict = _threshold_verdict(total)
    mismatch_dims = [d for d in dims.values() if d["score"] < 30]

    return EROIResult(
        job_id=features.job_id,
        job_title=features.job_title,
        company=features.company,
        total_score=total,
        verdict=verdict,
        dimensions=[DimensionScore(name=d["name"], score=d["score"], detail=d["detail"], weight=DIMENSION_WEIGHTS[d["name"]]) for d in dims.values()],
        skill_gaps=[SkillGap(skill=m["skill"], match=m["match"]) for m in dims["tech"].get("matches", []) if m["match"] != "direct"],
        mismatch_dimensions=[d["name"] for d in mismatch_dims],
    )


def score_job_from_text(job_id: str, job_title: str, company: str, raw_text: str, location: str = "") -> EROIResult:
    features = JobFeatures(raw_text=raw_text, job_title=job_title, company=company, location=location, job_id=job_id)
    return score_job(features)
```

### A.15 src/linkedin_mcp_custom/analysis/domain.py
```python
"""Domain dimension scorer — 35% weight. Checks if job is in industrial/adjacent domain."""
from __future__ import annotations

from linkedin_mcp_custom.analysis import normalize
from linkedin_mcp_custom.analysis.config import ADJACENT_INDUSTRIAL_KEYWORDS, CORE_INDUSTRIAL_KEYWORDS, NON_INDUSTRIAL_KEYWORDS


def domain_score(text: str) -> dict:
    normalized = normalize(text)
    noise_matches = sum(1 for kw in NON_INDUSTRIAL_KEYWORDS if normalize(kw) in normalized)
    core_matches = sum(1 for kw in CORE_INDUSTRIAL_KEYWORDS if normalize(kw) in normalized)
    adjacent_matches = sum(1 for kw in ADJACENT_INDUSTRIAL_KEYWORDS if normalize(kw) in normalized)

    if core_matches > 0:
        score = min(100, 60 + core_matches * 10)
        detail = f"Core industry keywords found ({core_matches} matches)"
    elif adjacent_matches > 0:
        score = min(70, 40 + adjacent_matches * 10)
        detail = f"Adjacent industry keywords found ({adjacent_matches} matches)"
    elif noise_matches > 0:
        score = max(5, 15 - noise_matches * 5)
        detail = f"Mostly non-industrial ({noise_matches} noise keywords) (pure noise)" if noise_matches >= 3 else f"Mostly non-industrial ({noise_matches} noise keywords)"
    else:
        score = 25
        detail = "No clear domain signal"

    return {"name": "domain", "score": score, "detail": detail}
```

### A.16 src/linkedin_mcp_custom/analysis/tech.py
```python
"""Tech dimension scorer — 25% weight. Matches skills from SKILL_MATRIX."""
from __future__ import annotations

from linkedin_mcp_custom.analysis import normalize
from linkedin_mcp_custom.analysis.config import SKILL_MATRIX


def tech_score(text: str) -> dict:
    normalized = normalize(text)
    direct = 0
    partial = 0
    matches_list = []

    for entry in SKILL_MATRIX:
        skill = entry["skill"]
        norm_skill = normalize(skill)
        partial_keywords = [normalize(k) for k in entry.get("partial_keywords", [])]

        if norm_skill in normalized:
            direct += 1
            matches_list.append({"skill": skill, "match": "direct"})
        elif any(pk in normalized for pk in partial_keywords):
            partial += 1
            matches_list.append({"skill": skill, "match": "partial"})

    if direct >= 3:
        score = 100
        detail = f"Strong tech profile ({direct} direct matches)"
    elif direct >= 1:
        score = min(85, 50 + direct * 15 + partial * 5)
        detail = f"Direct matches: {direct}, partial: {partial}"
    elif partial >= 2:
        score = min(50, 20 + partial * 10)
        detail = f"Indirect tech signals ({partial} partial matches)"
    elif partial == 1:
        score = 15
        detail = f"Minimal tech signals ({partial} partial match)"
    else:
        score = 5
        detail = "No relevant tech skills detected"

    return {"name": "tech", "score": score, "detail": detail, "matches": matches_list}
```

### A.17 src/linkedin_mcp_custom/analysis/role.py
```python
"""Role dimension scorer — 20% weight. Determines if role is engineering or fake-engineer."""
from __future__ import annotations

from linkedin_mcp_custom.analysis import normalize
from linkedin_mcp_custom.analysis.config import ENGINEERING_ROLE_KEYWORDS, FAKE_ENGINEER_KEYWORDS


def role_score(job_title: str, text: str) -> dict:
    norm_title = normalize(job_title)
    norm_text = normalize(text)
    title_has_engineering = any(normalize(kw) in norm_title for kw in ENGINEERING_ROLE_KEYWORDS)
    text_has_fake = any(normalize(kw) in norm_text for kw in FAKE_ENGINEER_KEYWORDS)

    if title_has_engineering and not text_has_fake:
        score = 85
        detail = "Engineering role confirmed"
    elif title_has_engineering and text_has_fake:
        score = 40
        detail = "Title is engineering but mixed with non-engineering signals"
    elif text_has_fake:
        score = 10
        detail = "Non-engineering or fake-engineer role detected"
    else:
        score = 35
        detail = "No strong role signal detected"

    return {"name": "role", "score": score, "detail": detail}
```

### A.18 src/linkedin_mcp_custom/analysis/growth.py
```python
"""Growth dimension scorer — 10% weight. Checks employer strategic/growth potential."""
from __future__ import annotations

from linkedin_mcp_custom.analysis import normalize
from linkedin_mcp_custom.analysis.config import GROWTH_EMPLOYERS, STRATEGIC_EMPLOYERS


def growth_score(company: str) -> dict:
    if not company:
        return {"name": "growth", "score": 5, "detail": "Unknown employer"}

    norm_company = normalize(company)
    for emp in STRATEGIC_EMPLOYERS:
        if normalize(emp) in norm_company:
            return {"name": "growth", "score": 90, "detail": f"Strategic employer: {emp}"}
    for emp in GROWTH_EMPLOYERS:
        if normalize(emp) in norm_company:
            return {"name": "growth", "score": 65, "detail": f"Growth employer: {emp}"}

    return {"name": "growth", "score": 20, "detail": "Non-strategic employer"}
```

### A.19 src/linkedin_mcp_custom/analysis/formal.py
```python
"""Formal education dimension scorer — 5% weight."""
from __future__ import annotations
import re

from linkedin_mcp_custom.analysis import normalize


def formal_score(text: str) -> dict:
    normalized = normalize(text)

    degree_patterns = [
        r"\b(bachelor|b\.?[a-sc]\.?|bac\.?)\b",
        r"\b(master|m\.?[a-sc]\.?|mag\.?|inženýr|inz[e]nyr|mgr|ing\.?)\b",
        r"\b(ph\.?d|doctor|doktor|doktorsk)\b",
        r"\b(vysok.?\u0161kola|vysokoskola|univerzita|university|college)\b",
        r"\b(vzdělání|vzdelani|education|degree|titul)\b",
    ]

    mentions = 0
    flexible = False
    for pattern in degree_patterns:
        matches = re.findall(pattern, normalized)
        mentions += len(matches)

    flexibility_signals = [
        r"\b(ekvivalent|equivalent|nebo\s+praxe|or\s+practice|výhodou|vyhodou|plus|welcome|preferred|nice\s+to\s+have)\b",
    ]
    for pattern in flexibility_signals:
        if re.search(pattern, normalized):
            flexible = True
            break

    if mentions >= 3 and not flexible:
        score = 10
        detail = "Degree required (multiple mentions), no flexibility clause"
    elif mentions >= 2:
        score = 30
        detail = "Degree preferred but flexibility implied"
    elif mentions >= 1:
        score = 50
        detail = "Degree mentioned but not strict requirement"
    else:
        score = 50
        detail = "No formal education signal"

    return {"name": "formal", "score": score, "detail": detail}
```

### A.20 src/linkedin_mcp_custom/analysis/location.py
```python
"""Location dimension scorer — 5% weight. Prefers remote/hybrid, penalizes office-only."""
from __future__ import annotations

from linkedin_mcp_custom.analysis import normalize
from linkedin_mcp_custom.analysis.config import CZECH_KEYWORDS, OFFICE_KEYWORDS, REMOTE_KEYWORDS


def location_score(location_field: str, text: str) -> dict:
    norm_text = normalize(text)
    norm_location = normalize(location_field)
    remote_signals = sum(1 for kw in REMOTE_KEYWORDS if normalize(kw) in norm_text)
    office_signals = sum(1 for kw in OFFICE_KEYWORDS if normalize(kw) in norm_text)
    cz_signals = sum(1 for kw in CZECH_KEYWORDS if normalize(kw) in norm_text or normalize(kw) in norm_location)

    if remote_signals >= 2:
        return {"name": "location", "score": 90, "detail": "Strong remote/hybrid culture"}
    if remote_signals >= 1:
        return {"name": "location", "score": 80, "detail": "Remote or hybrid work available"}
    if cz_signals and not office_signals:
        return {"name": "location", "score": 70, "detail": "CZ-based role"}
    if cz_signals and office_signals:
        return {"name": "location", "score": 50, "detail": "CZ on-site role"}
    if office_signals:
        return {"name": "location", "score": 30, "detail": "On-site/office role"}
    return {"name": "location", "score": 50, "detail": "No location signals"}
```

### A.21 src/linkedin_mcp_custom/analysis/kb_writer.py
[396 lines — full content in repo]
Key components:
- `KBWriter.__init__()` — loads metadata_stacku.json, finds next entry_id
- `KBWriter.write_all()` — orchestrates dedup, upsert, MD write, git commit
- `KBWriter._dedup_check()` — compares title/company/score with existing entries
- `KBWriter._upsert_metadata()` — updates metadata_stacku.json with new/changed entry
- `KBWriter._write_md_report()` — appends markdown section to agregovany_report.md
- `KBWriter._write_summary_table()` — regenerates summary table at top of MD report
- `KBWriter.commit_changes()` — git add + commit with message

### A.22 src/linkedin_mcp_custom/analysis/report_generator.py
[545 lines — full content in repo]
Key components:
- `SyntheticReportGenerator.__init__()` — loads metadata, sets paths
- `SyntheticReportGenerator.generate()` — orchestrates MD + JSON report creation
- Statistics: verdict distribution, skill frequency (top skills), SNR (signal-to-noise ratio per dimension), mismatch stats, cluster analysis
- Report format: ISO timestamp, header with entry count and date range, per-query breakdown with clickable hyperlinks, dimension tables, verdict distribution chart (ASCII)

### A.23 scripts/run_pipeline.py
[572 lines — full content in repo]
Key components:
- CLI with `--config`, `--headless/--no-headless`
- Config loading from YAML via `AppConfig.load()`
- 7 pipeline phases: browser_init, auth, scrape_saved, kb_init, per_job, git_commit, synthetic_report
- Parallel per-job processing with `asyncio.Semaphore(max_concurrent)` and `asyncio.wait_for(job_timeout)`
- Comprehensive error/warning/anomaly reporting to JSON + MD
- Verdict distribution, duration tracking, summary

---

## Appendix B — Cross-Repo Reference: MCP-Jobs

For architectural comparison, the auditing LLM may reference:
- **MCP-Jobs audit prompt:** `C:\Users\PC\Documents\Repozitar_Dev\_github\MCP-Jobs\docs\audit_prompt_v1.1.docx`
- **MCP-Jobs source:** `C:\Users\PC\Documents\Repozitar_Dev\_github\MCP-Jobs\src\mcp_jobs\`
- **Key differences:** requests+BS4 vs Patchright browser, 96 tests vs 29, 3 portals vs 1 platform (LinkedIn), CZ job market vs global LinkedIn

---

## Appendix C — Default Config

```yaml
# ~/.linkedin-mcp-custom/config.yaml
browser:
  block_resources: true
  headless: true
  pool_size: 3
pipeline:
  headless: true
  job_timeout_seconds: 120
  max_concurrent: 3
  stagger_delay: 1.5
scrape:
  max_nav_retries: 2
  max_pages: 5
  per_job_timeout_ms: 15000
  tracker_timeout_ms: 30000
thresholds:
  hranicni: 30.0
  medium: 45.0
  sledovat: 70.0
```

---

*Generated: 2026-07-15 19:45 | linkedin-mcp-custom v0.1.0 | Commit bd5b5dc | Tests: 29/29 | Based on MCP-Jobs audit_prompt_v1.1.docx template*
