# 🤖 linkedin-mcp-analyzer

> **LinkedIn saved jobs → EROI scoring → structured reports → git-committed market intelligence**
>
> Automated pipeline that scrapes your LinkedIn saved jobs, scores them against your profile using a 6-dimension EROI model, and writes actionable reports. Built as an [MCP server](https://modelcontextprotocol.io) — use it from Claude, VS Code, Cursor, opencode, or any MCP client.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-server-purple)](https://modelcontextprotocol.io)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/outpost2026/linkedin-mcp-custom/pulls)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🔍 What problem does this solve?

LinkedIn's job recommendations are **noisy**. Of 49 saved jobs analyzed, only **12% were relevant** (SLEDOVAT/follow). The rest are noise — AI hype roles, fake-engineer titles, distant locations, non-strategic employers.

This tool replaces manual scrolling and gut-feel decisions with a **repeatable, transparent scoring pipeline**:

```
📌 Your LinkedIn saved jobs
   ↓
🕷️ Patchright browser scraper   ← 4-layer resilience (CSS + text + JSON + full DOM)
   ↓
📊 EROI scoring engine          ← 6 dimensions, content-aware matching
   ↓
📝 Structured reports           ← agregovany_report.md + metadata_stacku.json
   ↓
📈 Synthetic market analysis    ← Frequency matrix + SNR + gap detection
   ↓
📦 Auto-committed to KB         ← git commit with full history
```

---

## ✨ Features

| Feature | What it does |
|---------|-------------|
| **Smart scraping** | 4-layer job ID extraction (href, attributes, JSON blobs, full DOM) — catches 100% of IDs |
| **6-dimension EROI scoring** | Domain (35%), Tech (25%), Role (20%), Growth (10%), Formal (5%), Location (5%) |
| **Fake-engineer detection** | Identifies roles with "Engineer" in title but service/sales content |
| **Skill gap analysis** | Direct match / partial match / no-match per job, aggregated into market-wide SNR |
| **Report generation** | Human-readable `.md` + machine-readable `.json` + synthetic market analysis |
| **Git commit** | Every pipeline run auto-commits to your knowledge base |
| **Session resilience** | Cookie lifecycle detection, checkpoint/challenge page handling, 60s TTL cache |
| **MCP-native** | Works with any MCP client — Claude Desktop, VS Code, Cursor, opencode |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (faster pip alternative — `pip install uv`)

### Install

```bash
git clone https://github.com/outpost2026/linkedin-mcp-custom.git
cd linkedin-mcp-custom
uv sync
```

### Authenticate (one-time)

```bash
.\linkedin-mcp.bat --login
# Opens a browser window — log into LinkedIn, then press Enter
```

### Verify session

```bash
.\linkedin-mcp.bat --status
# ✅ Session valid  |  page.url = https://www.linkedin.com/feed/
```

### Run the pipeline

```bash
# Via MCP client (recommended)
.\linkedin-mcp.bat
# Then in your MCP client: call analyze_saved_jobs

# Or standalone CLI (bypasses MCP transport ~ 2-3 min for 49 jobs)
.venv\Scripts\python scripts\run_pipeline.py
```

**Output:** `agregovany_report.md` + `metadata_stacku.json` in your KB directory, plus synthetic report.

---

## 📊 Example output (from 49 real jobs)

```
📊 49 saved jobs analyzed
   🟢 SLEDOVAT   6  (12%) — apply now
   🟡 MEDIUM    27  (55%) — consider
   🟡 HRANIČNÍ  12  (24%) — borderline
   🔴 NESLEDOVAT  4   (8%) — skip

🏆 Top leads:
   1. #003 Thermo Fisher — System Integration Engineer   76.5% 🟢
   2. #019 Siemens — RAM/LCC Engineer                    69.4% 🟢
   3. #013 Siemens — Test Automation Engineer             67.6% 🟢
   4. #015 Siemens — Embedded Tools Developer             65.9% 🟢
   5. #031 Renesas — Digital Design Engineer              65.5% 🟢
   6. #001 Desoutter — Light Automation Specialist        65.7% 🟢

🔬 Market intelligence:
   IoT (56% SNR), scripting (50%) = strongest relevance predictors
   AI appears in 49/49 jobs but only 12% SNR → noise signal
   Biggest skill gaps: C++ (16×), Azure (12×), AWS (9×)
```

Full report: [synteticky_report_analyza.md](https://github.com/outpost2026/B2B-Knowledge-Base/blob/main/02_ANAL%C3%9DZY/00_linkedin/synteticky_report_analyza.md)

---

## 🧠 EROI Scoring Model

### 6 dimensions

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| **Domain** | 35% | Industrial automation (core) vs adjacent vs noise |
| **Tech** | 25% | Skill overlap — content-aware match ratio × coverage |
| **Role** | 20% | Engineering role vs "fake engineer" (service/sales) |
| **Growth** | 10% | Strategic employer (Siemens, ABB, Thermo Fisher…) |
| **Formal** | 5% | Degree requirements with flexibility detection |
| **Location** | 5% | Remote/hybrid/CZ vs distant/office-only |

### Thresholds

| Score | Verdict |
|-------|---------|
| ≥65% | 🟢 **SLEDOVAT** (follow — apply now) |
| 50–64% | 🟡 **MEDIUM** (consider — mitigate gaps) |
| 40–49% | 🟡 **HRANIČNÍ** (borderline — only if time permits) |
| <40% | 🔴 **NESLEDOVAT** (skip — no time allocation) |

### Special patterns detected

- **Fake engineer**: title says "Engineer" but content is service/sales → penalizes `role`
- **Electronics manufacturing SMT/PCBA**: caps `domain` score (adjacent, not core)
- **Degree flexibility**: "equivalent practical experience" found → adds ~5% to `formal`
- **Positioning match**: strong `role` match compensates for weak `domain`
- **No-match penalty**: `tech` score drops sharply when key skills missing

---

## 🛠️ MCP Tools

| Tool | Description |
|------|-------------|
| `analyze_saved_jobs` | Full pipeline: scrape → EROI score → KB write → git commit |
| `get_saved_jobs` | List all saved job IDs from LinkedIn tracker |
| `get_job_details <id>` | Full posting text for a single job ID |
| `analyze_job <id>` | EROI score a single job (avoids timeout) |
| `check_session` | Verify LinkedIn auth status with diagnostics |

> **Timeout strategy:** `analyze_saved_jobs` uses time-budgeted batch processing (default 45s). For full analysis, use the CLI pipeline or call `analyze_job` per job.

---

## 📁 Output structure

```
B2B-Knowledge-Base/
└── 02_ANALÝZY/
    └── 00_linkedin/
        ├── agregovany_report.md          # Human-readable EROI entries
        ├── metadata_stacku.json          # Machine-readable (schema v1.1)
        └── synteticky_report_analyza.md  # Market intelligence report
```

---

## 🧪 Development

```bash
# Tests
.venv\Scripts\python -m pytest tests/ -v

# Lint
.venv\Scripts\python -m ruff check src/

# Type check
.venv\Scripts\python -m mypy src/
```

### Debugging known issues

See the [pitevni_kniha](docs/pitevni_kniha_v1.md) (autopsy book) for 14 documented bugs, root causes, fixes, and 16 cross-repo engineering rules.

| Known issue | Status |
|------------|--------|
| MCP transport timeout for batch ops | ✅ Fixed (time-budget + per-job tool) |
| Cookie lifecycle — silent expiry | ✅ Fixed (session cache + checkpoint detection) |
| KB dedup fallback (industry=None) | ✅ Fixed |
| Summary table non-idempotent | ✅ Fixed |
| Pagination missing pages | ✅ Fixed |
| CSS selector fragility | ✅ Fixed |

---

## 🤝 Contributing

PRs welcome! This project especially needs:

- **CI/CD pipeline** — GitHub Actions for weekly scraping
- **Docker deployment** — containerize the MCP server
- **More scorers** — add dimensions (salary, benefits, team size)
- **UI** — simple dashboard for browsing scored jobs
- **Translations** — localize EROI labels for your market

Please read [CONTRIBUTING.md](CONTRIBUTING.md) first (coming soon).

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

## 🧭 Why this exists

Built by a [systems integration engineer](https://github.com/outpost2026) who got tired of LinkedIn's noise-to-signal problem. The name "EROI" comes from energy-return-on-investment — a concept borrowed from off-grid solar (which the author also builds). The same principle applies to job hunting: **don't spend energy where the return is negative.**

> *"LinkedIn recommends everything. This tool tells you what matters."*

---

## 🔗 Links

- [Synthetic market report (49 jobs)](https://github.com/outpost2026/B2B-Knowledge-Base/blob/main/02_ANAL%C3%9DZY/00_linkedin/synteticky_report_analyza.md)
- [Aggregated report (49 entries)](https://github.com/outpost2026/B2B-Knowledge-Base/blob/main/02_ANAL%C3%9DZY/00_linkedin/agregovany_report.md)
- [Bug autopsy book](docs/pitevni_kniha_v1.md)
- [MCP practical workflow guide](https://github.com/outpost2026/B2B-Knowledge-Base/blob/main/04_KNOWLEDGE_BASE/01_MCP/MCP_practical_workflow_guide_v1.md)
- [Shared MCP postmortems](https://github.com/outpost2026/B2B-Knowledge-Base/blob/main/04_KNOWLEDGE_BASE/01_MCP/sdilena_pitevni_kniha_mcp.md)
