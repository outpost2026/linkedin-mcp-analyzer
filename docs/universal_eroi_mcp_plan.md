# Univerzální EROI LinkedIn MCP Server — Kalibrační a architektonický plán

**Autor**: LLM analýza na základě auditu linkedin-mcp-custom (Q3 2026)
**Kontext**: Transformace hardcoded single-user EROI scoreru na multi-subject univerzální MCP nástroj
**Cílová verze**: v2.0 — Q3/Q4 2026 a dále

---

## 1. Současná architektura (as-is)

### 1.1 Hardcoded závislosti

| Komponenta | Soubor | Typ vazby |
|---|---|---|
| `DIMENSION_WEIGHTS` | `analysis/config.py:8` | Fixní dict: domain=35%, tech=25%, role=20%, growth=10%, formal=5%, location=5% |
| `THRESHOLDS` | `analysis/config.py:12` | Fixní list: >=65 SLEDOVAT, >=50 MEDIUM, >=40 HRANICNI, <40 NESLEDOVAT |
| `SKILL_MATRIX` | `analysis/config.py:154` | 33 skills s fixními weight (0.3-1.0) — vše pro industrial/CNC |
| `CORE_INDUSTRIAL_KEYWORDS` | `analysis/config.py:22` | 46 keywords pro industrial automation |
| `ADJACENT_INDUSTRIAL_KEYWORDS` | `analysis/config.py:35` | 17 adjacent keywords |
| `NON_INDUSTRIAL_KEYWORDS` | `analysis/config.py:43` | 25 non-industrial keywords |
| `ENGINEERING_ROLE_KEYWORDS` | `analysis/config.py:52` | 14 inženýrských rolí |
| `STRATEGIC_EMPLOYERS` | `analysis/config.py:84` | 12 employer names |
| `KB_WRITER_PATH` | `analysis/kb_writer.py:30` | Fixní cesta k B2B-Knowledge-Base |
| `KB_REPO_ROOT` | `analysis/kb_writer.py:235` | Fixní parents[1] |

### 1.2 Data flow (současný)

```
LinkedIn API ──→ LinkedInExtractor ──→ EROI Scorer ──→ KBWriter
                      │                      │               │
                  raw text              6 dimensions      B2B-KB repo
                      │                  weighted sum      git commit
                      │                  fixed weights
                      │                  fixed thresholds
                      │                  fixed skills
                      ▼                      ▼               ▼
                [hardcoded]           [hardcoded]       [hardcoded]
```

### 1.3 Problém

Všechny parametry jsou **natvrdo v kódu** pro profil Ondřeje Souška (industrial/CNC/RE). Pro jiného uživatele je nutné:
1. Ručně měnit `config.py`
2. Upravovat KB writer path
3. Měnit skill matrix + keywords
4. Přepisovat testovací očekávání

---

## 2. Cílová architektura (to-be)

### 2.1 High-level koncept

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Server v2.0                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  CV (PDF/MD/JSON) ──→ CV Parser ──→ Calibration Matrix      │
│                                      (JSON/YAML)            │
│                                        │                    │
│                                        ▼                    │
│  LinkedIn ──→ Extractor ──→ EROI Scorer (parameterized)     │
│                                  │                          │
│                                  ▼                          │
│                         KB Writer (configurable path)       │
│                                  │                          │
│                                  ▼                          │
│                    Report (MD + JSON metadata)              │
│                                                              │
│  Nástroj: `calibrate_from_cv(cv_text)`                      │
│  Nástroj: `set_profile(profile_json)`                       │
│  Nástroj: `analyze_saved_jobs(ctx, profile_id)`             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Nové komponenty

| Komponenta | Účel | Vstup | Výstup |
|---|---|---|---|
| `CV Parser` | Extrahuje skills, domain, role preference z CV | Text/MD/PDF | StructuredProfile |
| `Calibration Generator` | Převede StructuredProfile na váhy + matici | StructuredProfile | calibration.json |
| `Profile Registry` | Spravuje více profilů (CRUD) | profile_id | ProfileConfig |
| `Parameterized Scorer` | Používá calibration.json místo config.py | JobFeatures + calibration | EROIResult |
| `Configurable KB Writer` | Cílí do user-specific KB path | EROIResult + config | Report |

---

## 3. Kalibrační matice — formát

### 3.1 Navrhovaný JSON schema

```json
{
  "schema_version": "2.0",
  "profile_id": "user_2026_001",
  "generated_from": "CV_Sousek_2026.pdf",
  "generated_at": "2026-07-07T10:00:00Z",
  "calibration": {
    "dimension_weights": {
      "domain": 0.35,
      "tech": 0.25,
      "role": 0.20,
      "growth": 0.10,
      "formal": 0.05,
      "location": 0.05
    },
    "thresholds": [
      {"min_score": 65, "verdict": "SLEDOVAT"},
      {"min_score": 50, "verdict": "MEDIUM"},
      {"min_score": 40, "verdict": "HRANICNI"},
      {"min_score": 0, "verdict": "NESLEDOVAT"}
    ],
    "domain_preferences": {
      "core_keywords": ["industrial automation", "CNC", "reverse engineering", ...],
      "adjacent_keywords": ["automotive", "embedded", ...],
      "non_target_keywords": ["sales", "frontend", ...],
      "electronics_mfg_keywords": []
    },
    "skill_matrix": [
      {"skill": "python", "weight": 1.0, "match_type": "direct_match"},
      {"skill": "reverse engineering", "weight": 1.0, "match_type": "partial_match"},
      ...
    ],
    "role_preferences": {
      "engineering_roles": ["engineer", "integrator", "architect", ...],
      "fake_engineer_roles": ["support engineer", ...]
    },
    "employer_preferences": {
      "strategic": ["Google", "Microsoft", "Siemens", ...],
      "growth": ["Fanuc", "Kuka", "ABB", ...]
    },
    "location_preferences": {
      "target_locations": ["Praha", "Brno", "Czech Republic"],
      "prefer_remote": true,
      "primary_region": "CZ"
    },
    "formal_education": {
      "require_degree": false,
      "prefer_flexibility": true
    },
    "kb_config": {
      "kb_path": "~/Documents/Repozitar_Dev/_github/B2B-Knowledge-Base/02_ANALYZY/00_linkedin",
      "repo_root_parents": 2,
      "report_filename": "agregovany_report.md",
      "metadata_filename": "metadata_stacku.json",
      "commit_message_prefix": "[ANALÝZY] add: EROI scoring batch"
    }
  }
}
```

### 3.2 CV → Calibration pipeline (ETL)

```
Fáze 1 — Extrakce (CV Parser)
├── Strukturované sekce: profil, zkušenosti, vzdělání, dovednosti, jazyky
├── Named Entity Recognition: společnosti, školy, lokace
├── Skill extraction: technické dovednosti + roky praxe
├── Domain inference: z textu určit primární doménu (industrial, IT, finance...)
└── Role inference: seniorita, typ role (IC, lead, manager, architect)

Fáze 2 — Transformace (Calibration Generator)
├── Mapování skills → skill_matrix s weight inferencí
│   └── weight = min(1.0, (years_experience / 10) * importance_multiplier)
├── Domain keywords → extrakce z CV textu (TF-IDF na sekcích)
├── Employer preferences → z historie zaměstnavatelů
├── Location preferences → z adresy + remote preference
├── Dimension weights → inferovány z profilu:
│   └── industrial profil → domain=0.35
│   └── IT/tech profil → tech=0.35, domain=0.20
│   └── akademický profil → formal=0.20, growth=0.15
└── Thresholds → default nebo custom per user

Fáze 3 — Load (Profile Registry)
├── Uložení calibration.json na disk (profiles/{profile_id}/)
├── Registrace do indexu (profiles/index.json)
└── MCP server reload s novým profilem
```

---

## 4. Implementační plán

### 4.1 Fáze 1 — Extrakce konfigurace (1-2 dny)

| Krok | Soubor | Akce |
|---|---|---|
| 1.1 | `analysis/config.py` | Extrahovat všechny konstanty do samostatného JSON loaderu |
| 1.2 | `analysis/config.py` | Přidat `load_config(profile_path)` který merge default + profile |
| 1.3 | `analysis/config.py` | Ponechat defaults jako fallback (reverse compat) |
| 1.4 | `analysis/scorer.py` | Přidat `profile_id` parametr, předat config do scorerů |
| 1.5 | Testy | Upravit testy na parametrický config |

### 4.2 Fáze 2 — CV Parser (3-5 dní)

| Krok | Soubor | Akce |
|---|---|---|
| 2.1 | `analysis/cv_parser.py` | Nový modul: extrakce strukturovaných dat z text/MD |
| 2.2 | `analysis/cv_parser.py` | Regex + LLM-assisted skill extraction |
| 2.3 | `analysis/calibrator.py` | Generování calibration.json z CV dat |
| 2.4 | `analysis/profile_registry.py` | CRUD profily, index, validace |
| 2.5 | Testy | Unit testy pro parser + calibrator |

### 4.3 Fáze 3 — MCP Tools (1-2 dny)

| Krok | Soubor | Akce |
|---|---|---|
| 3.1 | `tools/job.py` | Nový tool: `calibrate_from_cv(cv_text, profile_name)` |
| 3.2 | `tools/job.py` | Nový tool: `set_active_profile(profile_id)` |
| 3.3 | `tools/job.py` | Nový tool: `list_profiles()` |
| 3.4 | `tools/job.py` | Upravit `analyze_saved_jobs` — přidat `profile_id` parametr |
| 3.5 | `tools/job.py` | Upravit `get_job_details` — možnost rovnou EROI score |

### 4.4 Fáze 4 — KB Writer parametrizace (1 den)

| Krok | Soubor | Akce |
|---|---|---|
| 4.1 | `analysis/kb_writer.py` | Přidat configurable path z calibration |
| 4.2 | `analysis/kb_writer.py` | Přidat možnost více output repozitářů |
| 4.3 | `analysis/kb_writer.py` | Verzovat reporty podle profile_id |

### 4.5 Fáze 5 — Testování a regression (2 dny)

| Krok | Akce |
|---|---|
| 5.1 | Rozšířit test matrix: 3+ profily (industrial, IT, academic) |
| 5.2 | Regression testy pro legacy chování (default config) |
| 5.3 | Integrační testy: CV → calibration → EROI pipeline |
| 5.4 | Smoke testy: profile registry CRUD |

---

## 5. Hodnocení feasibility

### 5.1 Rizika

| Riziko | Pravděpodobnost | Dopad | Mitigace |
|---|---|---|---|
| CV parsing quality nízký | Střední | Vysoký | LLM-assisted parsing, human-in-the-loop |
| Skill weight inference nepřesná | Vysoká | Střední | Default weights + manuální override |
| Multi-subject konfigurace komplexní | Střední | Střední | JSON schema validation, UI pro editaci |
| LinkedIn scraping křehkost | Střední | Vysoký | Text-based parsing (již implementováno) |
| KB writer path security | Nízká | Vysoký | Sanitizace path, whitelist allowed roots |

### 5.2 Náklady

| Položka | Odhad (hodiny) |
|---|---|
| Fáze 1 — Config extrakce | 8-16 |
| Fáze 2 — CV Parser + Calibrator | 24-40 |
| Fáze 3 — MCP Tools | 8-16 |
| Fáze 4 — KB Writer | 4-8 |
| Fáze 5 — Testy | 12-16 |
| **Celkem** | **56-96 hodin** |

### 5.3 Celkové hodnocení

| Kritérium | Skóre (1-10) | Poznámka |
|---|---|---|
| Technická proveditelnost | 8/10 | Architektura čistá, žádné blockers |
| Business value | 9/10 | Multi-user = širší trh |
| Maintenance cost | 7/10 | Vyšší než single-user, ale zvládnutelné |
| Riziko selhání | 4/10 | Nízké — inkrementální změny |
| Alignment s MCP trendem | 10/10 | Q3/Q4 2026 je vrchol MCP adopce |
| **Celkem** | **7.6/10** | **Doporučuji implementovat** |

---

## 6. Finální doporučení

### 6.1 Proč to udělat

1. **Tržní poptávka**: MCP servery jsou v Q3 2026 nejžádanější dovednost na trhu
2. **Multi-user monetizace**: Z single-user nástroje se stane platforma
3. **EROI scoring je univerzální**: Metodika funguje pro jakýkoliv obor, jen váhy se liší
4. **První mover výhoda**: Na trhu není známý open-source EROI MCP server

### 6.2 Proč to nedělat (rizika)

1. **Scope creep**: Hrozí nekonečná customizace — striktní MVP
2. **LinkedIn scraping risk**: LinkedIn může změnit strukturu nebo blokovat
3. **CV parsing je těžký**: Kvalitní extrakce vyžaduje LLM → náklady

### 6.3 Verdikt

**Doporučuji implementovat** s následujícími pravidly:
1. MVP = config extrakce + profile registry (Fáze 1 + 3)
2. CV parser nechat na LLM-asistované bázi (ne custom NLP)
3. Zachovat zpětnou kompatibilitu s Ondřejovým profilem jako default
4. Publikovat jako open-source pro community adoption

---

## 7. Architect's Note

Současný kód je překvapivě dobře strukturovaný pro tuto transformaci. Oddělení `config.py` (všechny konstanty), `scorer.py` (orchestrace) a jednotlivých `*_scorer.py` modulů (čisté funkce bez side effects) umožňuje parametrizaci s minimálními změnami. Hlavní práce je v nových komponentách (CV parser, calibrator, registry), nikoli v refaktorování stávajících.

Doporučený postup: **Fáze 1 → Fáze 3 → test → Fáze 2 → Fáze 4 → Fáze 5**. Tedy nejdříve udělat config extrakci a MCP tools (viditelný výsledek pro uživatele), pak teprve CV parser (složitější, ale není blocking pro základní funkcionalitu).

---

*Vytvořeno: 2026-07-07 | Autor: LLM analysis | Verze: 1.0*
