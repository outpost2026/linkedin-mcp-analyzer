# Session 8 — Pipeline Run & Auth Cache Fix

**Datum:** 2026-07-09
**Cíl:** Spustit full MCP pipeline na refactor branch, lognout všechny anomálie, opravit nalezené chyby.
**Větev:** refactor (b7c1aec)
**Výsledek:** 3 pipeline runs, 2 kritické bugy opraveny, finální success rate 98% (49/50).

---

## 1. Pipeline Run Summary

| Run | Time | Duration | Success | Failed | Root Cause |
|-----|------|----------|---------|--------|------------|
| #1 | 07:07 (pre-session) | 182s | 28 (56%) | 22 | Nav races (ERR_ABORTED × 12, interrupted × 3, no content × 7) |
| #2 | 08:22 (post-login) | 114s | 0 (0%) | **50** | `check_cached_auth()` TTL=60s expired after 74s `scrape_saved` |
| #3 | 08:33 (after fix) | 482s | 45 (90%) | 5 | Singleton page auth refresh race (ERR_ABORTED on /feed/) |
| #4 | 08:43 (final fix) | 445s | **49 (98%)** | 1 | Transient nav race (job navigated to itself) |

**Progression:** 56% → 0% → 90% → **98%**

## 2. Bugs Discovered & Fixed

### B9: check_cached_auth() TTL expires between pipeline phases

- **Symptom:** 50/50 jobs fail immediately with "Session expired or never checked"
- **Root cause:** `SESSION_CHECK_INTERVAL = 60s` but `scrape_saved` takes 74s. Auth cache expires before per_job phase starts.
- **Fix (run_pipeline.py):** Added `await ensure_authenticated(page)` before per_job phase to refresh cache.
- **Fix (extractor.py):** Changed `scrape_job(parallel=True)` from raising `AuthenticationError` on stale cache to logging warning and proceeding (cookies still valid in persistent profile).
- **Pitevni kniha:** #029, #030

### B10: Singleton page auth refresh causes ERR_ABORTED race

- **Symptom:** 5/50 jobs fail with "Not authenticated" — `ensure_authenticated(self._page)` navigates to `/feed/` on singleton page while parallel tasks also try the same navigation.
- **Root cause:** Multiple asyncio tasks detect stale cache simultaneously, all call `ensure_authenticated(self._page)` → `page.goto('/feed/')` on same Page instance. No lock on auth refresh.
- **Fix:** Remove singleton-page auth refresh from `scrape_job()` entirely. Cache is advisory, not a hard gate. Persistent profile cookies are valid for the session duration.
- **Pitevni kniha:** #030

## 3. Error Timeline

### Run #1 (07:07, pre-session)
- 22 failures: 12× ERR_ABORTED, 3× interrupted navigation, 7× no content found
- Pattern: Jobs with `duration_seconds < 1s` = nav race. Jobs with `4-6s` = page loaded but no content.
- Already documented in session 7 anomalies.

### Run #2 (08:22, post-login, 50/50 failure)
- Auth OK at 08:20:52 (4.76s)
- scrape_saved completed at 08:22:08 (74.81s)
- **Every job failed** at 08:22:08 with "Session expired or never checked"
- Root cause: `check_cached_auth()` returns False because 74s > 60s TTL
- The browser session was FINE (cookies valid in persistent profile) — only the in-memory cache was stale

### Run #3 (08:33, after pipeline refresh fix, 45/50 success)
- Pipeline refresh before per_job: "Auth cache refreshed before per-job phase" ✅
- Jobs 1-17: Success (auth cache fresh from pipeline refresh)
- Job 18 (08:38:18): First "Auth cache stale" warning — 62s after refresh
- Jobs 18-50: Most succeed despite stale cache (cookies valid in profile)
- 5 failures from `ensure_authenticated(self._page)` → ERR_ABORTED on singleton page
- Error at 08:28:20: "Login check failed: Page.goto: net::ERR_ABORTED at /feed/" — singleton page race
- Error at 08:31:44: Same pattern, ~60s later when cache expired again

### Run #4 (08:43, final fix — no singleton auth, 49/50 success)
- All 50 jobs processed
- 49/50 scored and written to KB
- 1 failure: job 4408775531 — "Navigation interrupted by another navigation to same URL"
  - Pool round-robin reused a page that was mid-navigation
  - Duration: 23s (slow scrape, likely page loaded eventually)
  - Transient — would succeed on retry

## 4. Files Changed

| File | Changes |
|------|---------|
| `scripts/run_pipeline.py` | Added auth cache refresh before per_job phase |
| `src/linkedin_mcp_custom/scraping/extractor.py` | Removed singleton auth refresh from `scrape_job()`, replaced with warning log |

## 5. Pipeline Verdict Distribution (Run #4)

| Verdict | Count |
|---------|-------|
| MEDIUM | 25 |
| NESLEDOVAT | 14 |
| HRANICNI | 8 |
| SLEDOVAT | 2 |
| ERROR | 1 |

## 6. Key Metrics

- **Total pipeline duration:** 445s (7.4 min)
- **Scrape saved phase:** 74s (5 pages of saved jobs)
- **Per-job processing:** 365s (49 jobs × ~7.4s avg)
- **Parallel config:** 3 concurrent, 1.5s stagger
- **KB writes:** 49 (all successful)
- **Git commit:** `[ANALÝZY] pipeline: 49 jobs (2026-07-09)`

## 7. Open Issues

| Issue | Priority | Description |
|-------|----------|-------------|
| Pool round-robin causes self-navigation race | LOW | 1/50 jobs navigated to same URL on same page. Needs per-slot page assignment. |
| Auth cache TTL=60s too short for pipeline | FIXED | Now refresh before per_job phase + advisory only in parallel mode. |
| Singleton page auth refresh race | FIXED | Removed from parallel path entirely. |
| Pipeline creates 50 tasks upfront | LOW | ~80% waste on deadline-limited MCP runs. |

---

*Vytvořeno: 2026-07-09 | Session 8 — pipeline run + auth cache debugging*
