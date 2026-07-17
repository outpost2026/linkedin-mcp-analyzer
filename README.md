# 🤖 linkedin-mcp-analyzer

> **LinkedIn saved jobs → EROI scoring → structured reports → git-committed market intelligence**
>
> Automated pipeline that scrapes your LinkedIn saved jobs, scores them against your profile using a 6-dimension EROI model, and writes actionable reports. Anti-bot aware — uses human-like patterns to avoid detection.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-server-purple)](https://modelcontextprotocol.io)
[![Tests](https://img.shields.io/badge/tests-66%2F66-green)](tests/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🔍 What problem does this solve?

LinkedIn's job recommendations are **noisy**. Of 71 saved jobs analyzed, only **6% were relevant** (SLEDOVAT/follow). The rest are noise — AI hype roles, fake-engineer titles, distant locations, non-strategic employers.

This tool replaces manual scrolling with a **cache-aware, anti-bot pipeline**:

```
📌 Your LinkedIn saved jobs (71 tracked)
   ↓
🔄 Skip-existing filter          ← 95% reduction (only new jobs scraped)
   ↓
🕷️ Sequential scraper (30s, no parallelism)  ← anti-bot — human rhythm
   ↓
📊 EROI scoring engine           ← 6 dimensions, YAML-configured weights
   ↓
📝 KB write-back                 ← metadata_stacku.json + agregovany_report.md
   ↓
📈 Synthetic market analysis     ← Frequency matrix + SNR + gap detection
   ↓
📦 Auto-committed to KB          ← git commit with full history
```

---

## ✨ Features

| Feature | What it does |
|---------|-------------|
| **Cache-aware scraping** | Skips jobs already in KB (`--skip-existing`) — 95% time reduction |
| **Anti-bot pattern** | Sequential scraping (no parallelism), random delay 3-7s, fingerprint mix |
| **Adaptive delay** | Speeds up on success (0.95×), slows on errors (1.5×) — self-tuning |
| **Session heartbeat** | Refreshes LinkedIn auth every N jobs — prevents mid-run session expiry |
| **3-layer YAML config** | Source (max_pages) / Runtime (delay, timeout) / Analysis (N profiles) |
| **Configurable EROI** | `--profile industrial` switches thresholds + weights from YAML |
| **Fingerprint mix** | Random viewport, user-agent, locale, timezone per browser launch |
| **6-dimension EROI scoring** | Domain (35%), Tech (25%), Role (20%), Growth (10%), Formal (5%), Location (5%) |
| **Fake-engineer detection** | Identifies roles with "Engineer" in title but service/sales content |
| **Synthetic report** | Frequency matrix + SNR + gap detection + cluster analysis |
| **Raw text cache** | Stores raw job text in KB for re-scoring with different profiles |
| **Git commit** | Every pipeline run auto-commits to your knowledge base |

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
# Full pipeline (scrapes only new jobs, skips existing KB entries)
.venv\Scripts\python scripts\run_pipeline.py --skip-existing

# Fast mode (reduced delays, no fingerprint — for quick tests)
.venv\Scripts\python scripts\run_pipeline.py --skip-existing --fast

# Partial run (first 15 jobs — for testing)
.venv\Scripts\python scripts\run_pipeline.py --limit 15

# Custom config + analysis profile
.venv\Scripts\python scripts\run_pipeline.py --config ~/.linkedin-mcp-custom/config.yaml --profile industrial

# Via MCP client
.\linkedin-mcp.bat
# Then in your MCP client: call analyze_saved_jobs
```

**Output:** `agregovany_report.md` + `metadata_stacku.json` + `synteticky_report.md` in your KB directory.

### YAML Configuration

The pipeline uses a 3-layer YAML config (`~/.linkedin-mcp-custom/config.yaml`):

```yaml
user: "default"
source:
  max_pages: 10                      # how many tracker pages to scan
runtime:
  headless: true
  delay_range: [3.0, 7.0]           # anti-bot delay between jobs
  page_timeout_ms: 30000
  session_heartbeat: 30              # refresh auth every N jobs
  fingerprint_mix: true              # random viewport/UA/locale
analysis:
  default:                           # baseline EROI profile
    thresholds: { sledovat: 65, medium: 50, hranicni: 40 }
    weights: { domain: 0.35, tech: 0.25, role: 0.20, growth: 0.10, formal: 0.05, location: 0.05 }
  industrial:                        # custom profile — switch via --profile industrial
    thresholds: { sledovat: 70, medium: 55, hranicni: 45 }
    weights: { domain: 0.50, tech: 0.20, role: 0.15, growth: 0.05, formal: 0.05, location: 0.05 }
```

---

## 📊 Example output (from 71 real jobs)

```
PIPELINE REPORT
============================================================
Conclusion: ok
Duration: 142.31s total
Job IDs found: 71 (70 already in KB, 1 new)
Jobs scored: 1
Errors: 0

Verdicts: {'SLEDOVAT': 2, 'MEDIUM': 8, 'HRANICNI': 3, 'NESLEDOVAT': 2}
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

See the [pitevni_kniha](docs/pitevni_kniha_v1.md) (autopsy book) for 28 documented bugs, root causes, fixes, and engineering rules.

| Known issue | Status |
|------------|--------|
| MCP transport timeout for batch ops | ✅ Fixed (time-budget + per-job tool) |
| Cookie lifecycle — silent expiry | ✅ Fixed (session cache + checkpoint detection) |
| KB dedup fallback (industry=None) | ✅ Fixed |
| Summary table non-idempotent | ✅ Fixed |
| Pagination missing pages | ✅ Fixed |
| CSS selector fragility | ✅ Fixed |
| Refactor branch regression (34% → 100%) | ✅ Fixed (new baseline branch) |
| Anti-bot vs. speed tradeoff | ✅ Configurable (--fast, --profile) |
| Redundant scraping of known jobs | ✅ Fixed (--skip-existing) |

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

## 📈 Next iterations

Iterační backlog odvozený z 29 bug post-mortem záznamů a obscura-inspired pattern transferu. Každý návrh s hodnocením přínos/riziko.

| # | Návrh | Přínos | Riziko | Doporučení |
|---|-------|--------|--------|------------|
| 1 | **Optimalizovat page-turn na trackeru** — zkrátit `wait_for_timeout(17000)` nebo najít specifický selector pro detekci načtení | ↓40% času (ušetří ~60-80s) | Nízké — rychlejší navigace, stále sekvenční | ✅ **Teď** — nejvyšší poměr přínos/riziko |
| 2 | **Parallel per-job scraping** — `asyncio.gather` s N kontexty | 3-5× rychlejší (↓20-30s místo ~110s) | **Vysoké** — emergentní bot fingerprint (Z025) už jednou spadl z 98% na 34% | ❌ Počkat na lepší anti-bot strategii |
| 3 | **CI/CD weekly scrape** — rozchodit GitHub Actions workflow | Plně automatický monitoring | Střední — cookie export (Z021) vyžaduje ruční refresh každých pár týdnů | ⏳ Po stabilizaci skórovacího profilu |
| 4 | **Synthetic report 2.0** — trend analýza, skill gap evoluce, časové řady | Vyšší vypovídací hodnota než statický snapshot | Nízké — jen nová analytická vrstva | ⏳ Vyžaduje 2-3 historické snapshoty |
| 5 | **Multi-portál (Jobs.cz, Profesia)** — nový scraper per obscura worker pattern | Širší pokrytí trhu | Střední — předčasná abstrakce (obscura transfer sekce 8.3) | ❌ Počkat na 100+ jobů v KB |
| 6 | **Auth guard deduplication** — parametr `skip_auth_check` v `extract_page()` pro pipeline režim | Eliminace redundantní navigace na feed | Nízké — čistě refaktor bez změny chování | ✅ **Teď** — navazuje na fix Z029 |
| 7 | **Sbírat job IDs z API interceptu** místo DOM/script scanningu (Z018, Z013) | Rychlejší + spolehlivější extrakce | Střední — API formát se může změnit | ⏳ Až LinkedIn změní aktuální strukturu |

### Priority

| Kdy | Co |
|-----|----|
| **Teď** (1-2 běhy) | #1 page-turn optimalizace + #6 auth dedup |
| **Brzy** (3-5 běhů) | #3 CI/CD + #4 report 2.0 |
| **Až bude dost dat (100+)** | #5 multi-portál |
| **Až LinkedIn zlomí aktuální extrakci** | #7 API intercept |

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
