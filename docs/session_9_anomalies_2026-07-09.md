# Session 9 — MCP stdout Fix + Full Pipeline přes MCP stdio

**Datum:** 2026-07-09
**Cíl:** Opravit MCP transport (stdout corrupt), spustit kompletní pipeline přes MCP server, logovat anomálie.
**Výsledek:** 50/50 jobs oskórováno, syntetický report vygenerován (59 entries).

---

## 1. Bugs Discovered & Fixed

### B11: print() na stdout corruptuje MCP JSON-RPC protocol

- **Symptom:** `linkedin-analyzer` MCP server "vždy error" při volání z opencode
- **Root cause:** `cli.py:104` volá `print("Starting linkedin-mcp-custom MCP server...")` na stdout, který je MCP JSON-RPC kanál. Klient dostane ne-JSON data před validní odpovědí.
- **Fix:** Změněno na `print(..., file=sys.stderr)` + explicitní `mcp.run(transport="stdio")`
- **Status:** ✅ FIXED

### B12: Parallel scraping nemá auth redirect detection

- **Symptom:** Parallel `scrape_job()` přeskočí `ensure_authenticated()` — při expirované session dostane login page bez detection
- **Root cause:** `scrape_job()` volá `ensure_authenticated(page)` jen v sequential módu (`if not parallel:`). V parallel módu se spoléhá na cached auth, který může být stale.
- **Fix:** Přidána detekce login/checkpoint redirectů po `page.goto()` — funguje pro oba módy, nevyžaduje extra navigaci.
- **Status:** ✅ FIXED

---

## 2. Pipeline přes MCP stdio (bypass opencode 5s timeout)

Protože opencode default MCP timeout je 5000ms (málo na browser startup + LinkedIn navigace), pipeline puštěna přes přímou stdio komunikaci s MCP serverem.

| Krok | Výsledek | Detaily |
|------|----------|---------|
| `initialize` | ✅ | Handshake OK |
| `check_session` | ✅ | Session valid |
| `get_saved_jobs` | ✅ | 50 jobs IDs |
| `analyze_saved_jobs` (batch 1-4) | ✅ | 40 jobs oskórováno |
| `analyze_job` (jednotlivě 10) | ✅ | 10 jobs dozpracováno |
| `generate_report` | ✅ | 59 entries |

### Anomálie

| Type | Detail |
|------|--------|
| 🟡 **Response size limit** | `analyze_saved_jobs` s 50 joby vyrobí response přes asyncio pipe buffer limit. Řešení: batche po 10. |
| 🔴 **Job unreadable** | `#4434489179` vrací "Stránku se nepodařilo načíst" — 24.9% NESLEDOVAT |
| 🟡 **0% SNR technologie** | agentic, LLM, ML, AWS, Docker, Terraform, MCP — vyskytují se v nabídkách ale nikdy ne u SLEDOVAT |
| 🟡 **opencode timeout** | Default 5000ms timeout blokuje přímé volání `get_saved_jobs`/`analyze_saved_jobs` přes MCP tools. Config opraven (`"timeout": 120000`) — efektivní po restartu opencode. |

---

## 3. Pipeline Výsledky (50 fresh jobs)

### Verdict Distribution (kombinovaná)

| Verdict | Počet |
|---------|-------|
| 🟢 SLEDOVAT | 3 |
| 🟡 MEDIUM | 31 |
| 🟡 HRANIČNÍ | 9 |
| 🔴 NESLEDOVAT | 16 |

### Top 3

| # | Job | Score |
|---|-----|-------|
| 1 | System Integration Engineer @ Thermo Fisher Scientific | 76.5% |
| 2 | Technical Test Engineer / Automation Engineer @ Siemens | 73.6% |
| 3 | Light Automation Specialist @ Desoutter Tools | 65.7% |

### Skill Gaps (top)

| Skill | Výskyt v nabídkách |
|-------|-------------------|
| C++ | 15× |
| Azure | 10× |
| PLC | 8× |
| AWS | 7× |
| Kubernetes | 3× |

### Direct Matches (silné stránky autora)

| Skill | Match count |
|-------|-------------|
| Git | 30× |
| Python | 23× |
| IoT | 10× |
| CI/CD | 9× |
| Linux | 7× |
| CAM | 6× |

---

## 4. Files Changed

| File | Changes |
|------|---------|
| `src/linkedin_mcp_custom/cli.py` | `print→stderr`, `mcp.run(transport="stdio")` |
| `src/linkedin_mcp_custom/scraping/extractor.py` | Auth redirect detection po `page.goto()` pro oba módy |
| `C:\Users\PC\.config\opencode\opencode.jsonc` | Přidán `"timeout": 120000` pro linkedin-analyzer |

---

## 5. Open Issues

| Issue | Priority | Description |
|-------|----------|-------------|
| opencode MCP timeout 5s | MEDIUM | Po restartu opencode se projeví `timeout: 120000` v configu |
| Response size limit v analyze_saved_jobs | LOW | Batch processing po 10 řeší, ale ideální by byl streaming |
| Pool round-robin self-navigation race | LOW | 1/50 jobs padá na ERR_ABORTED při reuse page z poolu |

---

## 6. Report zapsán do KB

- `02_ANALÝZY/00_linkedin/synteticky_report_2026-07-09.md`
- `02_ANALÝZY/00_linkedin/synthetic_report_2026-07-09.json`

---

*Vytvořeno: 2026-07-09 | Session 9 — MCP stdout fix + full pipeline*
