# Session 7 — Anomalies & Debugging Report

**Datum:** 2026-07-09
**Cíl:** Gentle parallel scraping — implementovat concurrent job processing (3 semafor, stagger delay) pro 50 jobů v MCP timeout budgetu 45s.
**Status:** ✅ Všechny P0-P1 fixy aplikovány. Zbývají P2 (observabilita).

---

## 1. Bugs Fixed (8)

| ID | Bug | File | Severity | Fix |
|----|-----|------|----------|-----|
| B1 | `create_page()` pool never fills | `browser.py:107` | **CRITICAL** | pool-fill before pool-cycle |
| B2 | `analyze_saved_jobs` sequential loop | `job.py:313` | **HIGH** | `asyncio.gather` + semaphore |
| B3 | `log_phase()` overwrites phase data | `run_pipeline.py:42` | MEDIUM | `setdefault().update()` merge |
| B4 | Deadline vs errored confusion | `job.py:229` | MEDIUM | `__deadline__` sentinel |
| B5 | No retry for nav races | `extractor.py:208` | **HIGH** | Retry loop (2×, 1s/2s) |
| B6 | Python `\n` in `page.evaluate()` | `extractor.py:395,454` | **HIGH** | Raw strings `r"""..."""` |
| B7 | Auth guard missing on pooled pages | `extractor.py:206` | MEDIUM | `check_cached_auth()` |
| B8 | Auth timing missing in report | `run_pipeline.py:153` | LOW | `t_auth_start` + log |

## 2. Pipeline Performance Regression

| Run | Date | Mode | Duration | Success | Failed | Nav Errors | Auth Errors | Metadata OK |
|-----|------|------|----------|---------|--------|------------|-------------|-------------|
| #1 | 07-07 | Sequential | 533s | **49 (100%)** | 0 | 0 | 0 | ✅ (untracked) |
| #2 | 07-09 07:03 | Parallel (broken auth) | 204s | 20 (40%) | 30 | 0 | **28** | ✅ (untracked) |
| #3 | 07-09 07:07 | Parallel (broken pool) | 182s | 28 (56%) | 22 | **22** | 0 | ❌ (empty metadata) |
| #4 | 07-09 07:30 | Parallel (partial fixes) | >180s | ~25 partial | — | **0** | 0 | ❌ (B6 — metadata syntax error) |
| #5 | expected | All fixes | ~150s | ~50 (100%) | ~0 | 0 | 0 | ✅ |

**Regrese:** Sekvenční #1 = 100%. Paralelní #2-#4 = 40-56%. Příčina: 3 nezávislé bugy (auth race, pool race, raw string escape). Po fixech všech 3: očekáváno 100%.

## 3. Error Classification (All Runs Combined)

| Error Type | Count | Root Cause | Fix Applied |
|------------|-------|------------|-------------|
| `AuthenticationError: Not authenticated` | 28 | `ensure_authenticated()` on pooled page → `/feed/` navigation race | B7 (cached auth guard, no nav) |
| `net::ERR_ABORTED` | 13 | Single Page instance → concurrent `page.goto()` | B1 (5-page pool) |
| `navigation interrupted by another navigation` | 3 | Same as ERR_ABORTED | B1 |
| `No content found` | 6 | Page landed on wrong URL (race) | B1 + B5 (retry) |
| `SyntaxError: Invalid regular expression: missing /` | 50+ | Python `\n` → broken JS string `split('\n')` | B6 (raw strings) |
| `Job metadata extraction failed` | 50+ | Same as above (wraps SyntaxError) | B6 |
| Pipeline timeout (180s) | 1 | 50 jobs × ~20s/batch > 180s | — (needs batch processing) |

## 4. Files Changed This Session

| File | Changes |
|------|---------|
| `src/linkedin_mcp_custom/core/browser.py` | `create_page()` pool-fill fix (B1) |
| `src/linkedin_mcp_custom/core/auth.py` | New `check_cached_auth()` public function (B7) |
| `src/linkedin_mcp_custom/core/__init__.py` | Export `check_cached_auth` |
| `src/linkedin_mcp_custom/tools/job.py` | `asyncio.gather`, deadline sentinel, removed dead code (B2, B4) |
| `src/linkedin_mcp_custom/scraping/extractor.py` | Raw strings (B6), retry loop (B5), auth guard (B7), `_is_navigation_race()` |
| `scripts/run_pipeline.py` | `log_phase` merge fix (B3), auth timing (B8) |
| `docs/pipeline_*.json` | 3 new pipeline run reports (pre-fix) |
| `docs/pipeline_*.md` | 3 new pipeline human-readable reports |
| `docs/pitevni_kniha_v1.md` | New records 025-028 |

## 5. New Post-Mortem Records (025-028)

| Record | Title | Severity |
|--------|-------|----------|
| 025 | `create_page()` pool never fills beyond 1 | CRITICAL |
| 026 | Python `\n` in `page.evaluate()` — raw string escape leak | HIGH |
| 027 | Pipeline reporter `log_phase()` overwrites phase data | MEDIUM |
| 028 | Auth guard missing on pooled pages | MEDIUM |

## 6. Open Issues (Neřešeno)

| Issue | Priority | Popis |
|-------|----------|-------|
| Browser profile lock (017) | MEDIUM | Nelze spustit CLI pipeline + MCP server současně |
| 50 tasks created upfront | LOW | ~80% tasks zbytečné při deadline-limited runu |
| Per-job timing breakdown | LOW | Report neobsahuje per-fáze timingy pro jednotlivé joby |
| Pipeline timeout 180s | LOW | Full run ~150s → potřeba zvýšit timeout na 240s |
| CI/CD chybí | MEDIUM | Žádný automatický pipeline run |

---

*Vytvořeno: 2026-07-09 | Na základě session 7 — debugging + fixy*
