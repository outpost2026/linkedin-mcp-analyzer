# Plán V2: Multi-user EROI MCP — integrace pitevních nálezů

**Verze:** 1.0 | **Datum:** 2026-07-07 | **Navazuje na:** `universal_eroi_mcp_plan.md`, `pitevni_kniha_v1.md`

---

## 1. Východiska

### 1.1 Současný stav (v0.5.0)

6 hardcoded scorerů → `config.py` (243 řádků konstant) → `kb_writer.py` (fixní B2B-KB cesta) → 3 MCP tools bez `profile_id` parametru. Všechny pitevní nálezy (001–006) opraveny. Funkční pipeline: LinkedIn → Extractor → EROI → KB write-back + git commit.

### 1.2 Pitevní nálezy linkedin-mcp-custom (001–006)

| # | Nález | Stav | Dopad pro V2 |
|---|-------|------|-------------|
| 001 | Typová záměna BrowserContext vs. Browser | ✅ Fixed | Nový kód musí používat `BrowserContext`, nikdy `Browser` |
| 002 | Stínová lokální proměnná _page (Missing global) | ✅ Fixed | Každý zápis do globální proměnné → `global` deklarace |
| 003 | Auth navigační konflikt (is_logged_in redirect) | ✅ Fixed | Auth always before navigation — pravidlo držet i v nových toolách |
| 004 | Fragilita CSS selektorů (LinkedIn DOM mutace) | ✅ Fixed | Žádné CSS třídy — jen `a[href*="/company/"]` + `main.innerText` |
| 005 | Paginační slepota (Missing second page) | ✅ Fixed | Heuristické pagination klikání v `scrape_saved_jobs()` |
| 006 | Špatný git repo root v parents[2] | ✅ Fixed | `parents[1]` místo `parents[2]` — verifikovat pro user-specific KB paths |

### 1.3 Cross-repo pravidla MCP serverů (P1–P10)

Ze `sdilena_pitevni_kniha_mcp.md` — platí pro V2 implementaci jako **architektonické invarianty**:

| ID | Pravidlo | Aplikace na V2 |
|----|----------|----------------|
| P1 | Subprocess timeout ≤ 25 % MCP client timeoutu | Git operace v KB writeru: max 15 s |
| P2 | ThreadPoolExecutor pro N>1 nezávislých zdrojů | `analyze_saved_jobs` iterující N jobů |
| P3 | `git --no-optional-locks` pro read-only volání | Všechny git operace v KB writeru |
| P4 | JSON defenziva — `try/except` + `isinstance` guard | Profile registry, calibration.json deserializace |
| P5 | `@auditable` diagnostika s `ts`, `tool`, `duration_s`, `ok` | Všechny nové MCP tools (F3) |
| P6 | Timeout guard pro I/O >10 s | `calibrate_from_cv` (LLM call), git operace |
| P7 | `global` deklarace při zápisu do glob. proměnných | Profile registry singleton, active_profile |
| P8 | Auth first, navigation second | Udržet stávající pattern v extractoru |
| P9 | Žádné CSS třídy — jen sémantické HTML atributy | Udržet stávající pattern |
| P10 | `Path.parents` je 0-indexovaný — verifikovat `relative_to()` | Všechny user-specific KB cesty |

---

## 2. Cílová architektura (to-be)

### 2.1 Komponent diagram

```
                        ┌──────────────────────┐
                        │   Profile Registry    │
                        │  profiles/index.json  │
                        │  profiles/{id}/       │
                        │    calibration.json   │
                        └─────────┬────────────┘
                                  │
        CV (MD/PDF) ──→ CV Parser ─┤        ◄── P4: JSON defenziva
                                  │             P7: global deklarace
                                  ▼
                        ┌──────────────────────┐
                        │  Calibration Matrix   │
                        │  (JSON Schema v2.0)   │
                        │  - dimension_weights  │
                        │  - thresholds         │
                        │  - domain_preferences │
                        │  - skill_matrix       │
                        │  - role_preferences   │
                        │  - employer_prefs     │
                        │  - location_prefs     │
                        │  - formal_education   │
                        │  - kb_config          │
                        └─────────┬────────────┘
                                  │
LinkedIn ──→ Extractor ──→ Parametrized Scorer ──→ Configurable KB Writer
   (P8,P9)       (P8)          (weights z              (P1,P3,P6,P10)
                                calibration.json)

                                  │
                              ┌───┴───┐
                              │ P2:   │
                              │ Pool  │
                              └───────┘

Nové MCP tools (P5,P6):
  - calibrate_from_cv(cv_text, profile_name)
  - set_active_profile(profile_id)
  - list_profiles()
  - analyze_saved_jobs(ctx, write_to_kb, profile_id)
  - get_job_details(job_id, profile_id)
```

### 2.2 Změny oproti existujícímu plánu

| Aspekt | `universal_eroi_mcp_plan.md` | Tento plán (po integraci pitevních nálezů) |
|--------|------------------------------|-------------------------------------------|
| Quality gates | Nejsou specifikovány | Diagnostické filtry z pitevní knihy jako vstupní/výstupní kritéria každé fáze |
| Timeout politika | Není řešena | P1: subprocess ≤15s, P6: timeout wrapper pro I/O >10s |
| JSON defenziva | Není řešena | P4: try/except + isinstance guard na každém deserializátoru |
| Paralelizace | Není řešena | P2: ThreadPoolExecutor pro analyze_saved_jobs (N jobů) |
| Git bezpečnost | Není řešena | P3: --no-optional-locks, P10: verifikace parents indexu |
| Audit log | Není řešen | P5: @auditable na všech nových toolách |
| Pořadí implementace | F1 → F3 → test → F2 → F4 → F5 | **F0 → F1 → F3a → F2 → F4 → F3b → F5** (F0 = pitevní prevence, F3a = tools bez CV parseru, F3b = CV tools až po registry) |

---

## 3. Implementační fáze

### Fáze F0 — Pitevní prevence (2-4h)

Cíl: Aplikovat P1–P10 pravidla na stávající kód **před** refactoringem.

| Krok | Soubor | Akce | Pravidlo |
|------|--------|------|----------|
| F0.1 | `analysis/kb_writer.py` | Přidat `--no-optional-locks` do git volání | P3 |
| F0.2 | `analysis/kb_writer.py` | Snížit subprocess timeout na 15s + timeout wrapper | P1, P6 |
| F0.3 | `tools/job.py` | Přidat `@auditable` wrapper na tooly | P5 |
| F0.4 | `tools/job.py` | Přidat `ThreadPoolExecutor` pro analyze_saved_jobs (N jobů) | P2 |
| F0.5 | `analysis/config.py` | Zamknout config jako immutable (dataclass) | — |
| F0.6 | Vše | Projit diagnostický filtr z `pitevni_kniha_v1.md:49-69` | — |

**Quality gate:** Všechny body diagnostického filtru (A1–A4, B5–B11, C12–C14) procházejí.

---

### Fáze F1 — Config extrakce (8-16h)

Cíl: Config loader, merge default+profile, scorery berou config parametrem.

| Krok | Soubor | Akce |
|------|--------|------|
| F1.1 | `analysis/config.py` | Extrahovat konstanty do `Config` dataclass + JSON loader |
| F1.2 | `analysis/config.py` | Implementovat `load_config(profile_id)` s hlubokým merge |
| F1.3 | `analysis/config.py` | Defaultní config = současné hodnoty (fallback) |
| F1.4 | Všechny scorery | Přidat `config: Config` parametr, odstranit přímý import z `config.py` |
| F1.5 | `analysis/scorer.py` | Předat config do scorerů místo globálních konstant |
| F1.6 | Testy | Upravit regression testy na explicitní config |
| F1.7 | Vše | Ověřit P10: `Path.parents` indexy v user-specific cestách |

**Pitevní vazba:** 006 (parents index), obecná zranitelnost hardcoded konstant.
**Quality gate:** Regression testy procházejí se stejnými hodnotami jako před refactoringem.

---

### Fáze F2 — Profile Registry (8-16h)

Cíl: CRUD profily, `profiles/` adresář, index.json, JSON schema validace.

| Krok | Soubor | Akce |
|------|--------|------|
| F2.1 | `analysis/profile_registry.py` | CRUD operace: create/read/update/delete/list |
| F2.2 | `analysis/profile_registry.py` | `profiles/index.json` — seznam všech profilů |
| F2.3 | `analysis/profile_registry.py` | JSON schema validace calibration.json |
| F2.4 | `analysis/profile_registry.py` | Active profile singleton (P7: global deklarace) |
| F2.5 | `analysis/profile_registry.py` | P4: JSON defenziva — try/except + isinstance guard |
| F2.6 | Testy | Unit testy: CRUD, validace, edge cases (corrupt JSON) |

**Pitevní vazba:** P4 (JSON defenziva), P7 (global deklarace).
**Quality gate:** Všechny CRUD operace + corrupt JSON recovery.

---

### Fáze F3a — MCP Tools — parameterized (4-8h)

Cíl: Přidat `profile_id` do stávajících toolů + nové nástroje pro registry.

| Krok | Soubor | Akce |
|------|--------|------|
| F3a.1 | `tools/job.py` | `analyze_saved_jobs`: přidat `profile_id` (nepovinný) |
| F3a.2 | `tools/job.py` | `get_job_details`: přidat `profile_id` (nepovinný) + EROI score |
| F3a.3 | `tools/job.py` | Nový tool: `set_active_profile(profile_id)` |
| F3a.4 | `tools/job.py` | Nový tool: `list_profiles()` |
| F3a.5 | `server.py` | Registrace nových toolů |
| F3a.6 | Vše | P5: @auditable, P6: timeout wrapper |

**Pitevní vazba:** P5 (diagnostika), P6 (timeout guard).
**Quality gate:** Každý tool má `@auditable` + timeout guard.

---

### Fáze F3b — CV Parser + Calibrator (16-24h) — **PARALELNÍ K F4**

Cíl: CV → StructuredProfile → calibration.json.

| Krok | Soubor | Akce |
|------|--------|------|
| F3b.1 | `analysis/cv_parser.py` | Nový modul: extrakce skills/domain/role/location z text/MD |
| F3b.2 | `analysis/cv_parser.py` | Regex + LLM-assisted extraction |
| F3b.3 | `analysis/calibrator.py` | StructuredProfile → calibration.json s inferencí vah |
| F3b.4 | `tools/job.py` | Nový tool: `calibrate_from_cv(cv_text, profile_name)` |
| F3b.5 | Testy | Unit testy pro parser + calibrator |

**Pitevní vazba:** P6 (timeout guard pro LLM call).
**Riziko:** CV parsing quality — mitigace LLM-assisted + human-in-the-loop.

---

### Fáze F4 — KB Writer parametrizace (4-8h) — **PARALELNÍ K F3b**

Cíl: Configurable KB path, format, commit message z calibration.

| Krok | Soubor | Akce |
|------|--------|------|
| F4.1 | `analysis/kb_writer.py` | `KB_PATH` + `REPO_ROOT_PARENTS` z calibration.json |
| F4.2 | `analysis/kb_writer.py` | P10: verifikovat `relative_to()` před každým commitem |
| F4.3 | `analysis/kb_writer.py` | P1: subprocess timeout max 15s |
| F4.4 | `analysis/kb_writer.py` | P3: `--no-optional-locks` |
| F4.5 | `analysis/kb_writer.py` | Verzovat reporty podle profile_id |
| F4.6 | `analysis/kb_writer.py` | P6: timeout wrapper pro git commit (může trvat >10s) |
| F4.7 | Testy | Unit testy pro různé KB cesty |

**Pitevní vazba:** 006 (parents index — P10), P1 (timeout), P3 (git locks).
**Quality gate:** `parents` index verifikován pro 3+ různých KB path hloubek.

---

### Fáze F5 — Testy + regression (12-16h)

Cíl: 3+ profily, legacy regression, integrační testy.

| Krok | Akce |
|------|------|
| F5.1 | Rozšířit test matrix: industrial (default), IT, academic |
| F5.2 | Regression testy: legacy chování se stejným configem |
| F5.3 | Integrační testy: CV → calibration → EROI pipeline |
| F5.4 | Smoke testy: profile registry CRUD |
| F5.5 | Pitevní regrese: ověřit že žádný fix (001–006) není rozbit |
| F5.6 | Zátěžový test: analyze_saved_jobs s 25+ joby (P2: timeout) |

---

## 4. Časový harmonogram

```
Fáze           Odhad      Závislost       Pitevní vazba
─────────────────────────────────────────────────────────
F0 — Prevence    2-4h     —               P1–P10 aplikace
F1 — Config     8-16h     F0              006, parents index
F2 — Registry   8-16h     F1              P4, P7
F3a — Tools     4-8h      F2              P5, P6
F3b — CV Parser 16-24h    F2 (paralelně)  P6 (LLM timeout)
F4 — KB Writer  4-8h      F1 (paralelně)  006, P1, P3, P10
F5 — Testy      12-16h    F3a+F3b+F4      Všechny
─────────────────────────────────────────────────────────
Celkem         54-92h
```

**Doporučené pořadí:** F0 → F1 → F2 → (F3a + F4 paralelně) → F3b → F5

Toto pořadí:
1. Nejprve prevence (F0) — levné, vysoký dopad
2. Config extrakce (F1) — základ všeho, žádná změna logiky
3. Profile registry (F2) — úložiště pro profily
4. Tools + KB writer paralelně (F3a + F4) — viditelný výsledek
5. CV parser (F3b) — nejsložitější, neblokuje základní funkcionalitu
6. Testy (F5) — až je vše hotovo

---

## 5. Rizika a mitigace

| Riziko | Pravděp. | Dopad | Mitigace | Pitevní vazba |
|--------|----------|-------|----------|---------------|
| Záměna BrowserContext/Browser v novém kódu | Nízká | Vysoký | Code review s diagnostickým filtrem | 001 |
| Missing global v profile registry | Nízká | Vysoký | Lint rule: `global` check v pre-commit | 002, P7 |
| Auth/navigation ordering v nových toolách | Nízká | Vysoký | Template pro tool implementaci | 003, P8 |
| CSS třídy v nových selektorech | Nízká | Střední | Code review: grep na `.job-details` | 004, P9 |
| Špatný parents index v user-specific KB path | Střední | Vysoký | `relative_to()` verifikace v testech | 006, P10 |
| CV parsing quality | Střední | Vysoký | LLM-assisted + human-in-the-loop | — |
| Timeout v analyze_saved_jobs (25+ jobů) | Střední | Vysoký | ThreadPoolExecutor + progress reporting | P2, P6 |

---

## 6. Diagnostický filtr pro V2

### Browser vrstva (browser.py)
- [ ] A1: `_context` místo `_browser` (001)
- [ ] A2: `global` deklarace ve všech funkcích (002, P7)
- [ ] A3: `_page` nastaven po `get_or_create_browser()` (002)

### Scraping vrstva (extractor.py)
- [ ] B4: Auth před navigací (003, P8)
- [ ] B5: Žádné CSS třídy v selektorech (004, P9)
- [ ] B6: Text-based parsing z `main.innerText` (004)

### KB Writer (kb_writer.py)
- [ ] C7: `parents[1]` nebo verifikováno `relative_to()` (006, P10)
- [ ] C8: `subprocess.run` s `cwd=repo_root` (006)
- [ ] C9: `--no-optional-locks` (P3)
- [ ] C10: subprocess timeout ≤15s (P1)

### Profile Registry
- [ ] D11: JSON defenziva — try/except + isinstance guard (P4)
- [ ] D12: Auto-repair mechanismus pro corrupt JSON (P4)
- [ ] D13: `global` deklarace pro active_profile singleton (P7)

### MCP Tools
- [ ] E14: `@auditable` na všech nových toolách (P5)
- [ ] E15: timeout wrapper pro I/O >10s (P6)
- [ ] E16: ThreadPoolExecutor pro N>1 jobů (P2)

---

*Vytvořeno: 2026-07-07 | Integruje: universal_eroi_mcp_plan.md, pitevni_kniha_v1.md, sdilena_pitevni_kniha_mcp.md*
