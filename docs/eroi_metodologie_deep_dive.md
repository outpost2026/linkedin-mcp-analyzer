# EROI Scoring — Hloubková dokumentace metodologie

**Verze:** 1.0 | **Datum:** 2026-07-07
**Autor:** Ondřej Soušek (metodika) + Dev (extrakce z kódu + KB artefaktů)
**Zdroje:** `agregovany_report.md`, `synteticky_report_analyza.md`, `metadata_stacku.json`, `config.py`, všech 6 scorerů

---

## 1. Geneze — Proč EROI vzniklo

EROI scoring nebyl teoretický koncept. Vznikl z **čistě praktické potřeby**:

```
1. Uživatel si uloží LinkedIn nabídku (manuálně, klikem)
2. Otevře ji, copy-paste celý text do OpenCode/LLM chatu
3. LLM analyzuje: doména, tech stack, role, lokalita
4. Uživatel ručně zapíše výsledek do agregovany_report.md + metadata_stacku.json
5. Opakovat pro každou nabídku zvlášť
```

**Problém:** Neškálovatelné. 24 nabídek = hodiny copy-paste + ruční analýzy.

**Řešení:** Automaticá pipeline = MCP server scrapne saved jobs → extrahuje text → EROI engine spočítá fit → KB writer zapíše report + metadata + git commit.

EROI scoring engine je **automatizace toho, co LLM dělal ručně v chatu** — ale s explicitními, konzistentními a opakovatelnými pravidly.

---

## 2. Základní rovnice EROI

```
EROI = P(converze) × Hodnota / Náklady
```

Kde:
| Proměnná | Význam | Zdroj dat |
|----------|--------|-----------|
| P(converze) | Pravděpodobnost, že autor projde výběrovým řízením | Odvozena z domain + tech + role match + seniorita |
| Hodnota | Očekávaná měsíční odměna (CZK) + kariérní dopad | Metadata + tržní odhad |
| Náklady | Čas nutný na přípravu (CV customizace, doučení skills) | Odhad z gap analýzy |

**V praxi kód počítá:**
1. **dimension scores** (0-100) pro každou ze 6 dimenzí
2. **weighted total** = Σ(dimension score × weight)
3. **verdict** podle threshold:
   - ≥65 → SLEDOVAT
   - 50-64 → SLEDOVAT medium
   - 40-49 → HRANIČNÍ
   - <40 → NESLEDOVAT

Přímý EROI výpočet (`P × Value / Cost`) je v `metadata_stacku.json` ale v kódu se počítá aproximativně přes dimension scores.

---

## 3. 6 Scoring Dimensions

```
TOTAL = domain×0.35 + tech×0.25 + role×0.20 + growth×0.10 + formal×0.05 + location×0.05
```

### 3.1 Domain (35 %) — `domain.py`

Váha 35 % je **nejvyšší a záměrně přísná**. Důvod: ~67 % nabídek na LinkedIn je z nerelevantních domén. Každá nerelevantní doména = nulový kariérní crossover, bez ohledu na tech stack.

**Jak funguje:**
```
CORE industrial keywords (44 ks) → 5+ hits = 85 %, 3-4 hits = 70 %, 1-2 hits = 45+ %
ADJACENT keywords (15 ks) → 3+ hits = 45 %, 1-2 hits = 30+ %
NON-INDUSTRIAL keywords (28 ks) → 3+ hits = 10 %, 1-2 hits = 20 %
Electronics manufacturing (7 ks) → cap at 45 %
```

**Kalibrační příběh:** Původně domain=30 %. Po analýze 24 nabídek zjištěno, že 70 % je z nerelevantních domén. Zvýšení na 35 % zabránilo false positive (Toloka #024 by při 30 % dosáhla 51 % → SLEDOVAT, ale doménově je mimo).

**Klíčové industriální keywords:** PLC, SCADA, CNC, CAM, robotics, TIA Portal, PROFINET, OPC UA, manufacturing, industrial automation.

### 3.2 Tech (25 %) — `tech.py`

Druhý nejsilnější prediktor. Měří překryv autorova skill setu s požadavky nabídky.

**Skill matrix:** 33 skills s weight 0.3-1.0, rozdělené do 3 match typů:
| Match type | Význam | Příklad |
|------------|--------|---------|
| direct_match | Autor skill ovládá a je v nabídce | Python, CI/CD, test automation |
| partial_match | Koncepčně blízko, není přesný match | LLM, machine learning, virtualization |
| no_match | Skill v nabídce, autor ho neovládá | TypeScript, Kubernetes, Azure, PLC |

**Vzorec:**
```
match_ratio = matched_weighted / mentioned_weighted
coverage = mentioned_weighted / max_possible
coverage_multiplier = min(1.0, coverage × 5)
score = match_ratio × coverage_multiplier × 100
```

**Výstup:** score 0-100 + seznam skill_gapů (direct/partial/no match).

**Kalibrace z reálných dat (SNR analýza):**
| Skill | Poptávka | SNR |
|-------|----------|-----|
| PLC | 3× | 66.7 % — nejsilnější prediktor |
| Python | 6× | 50.0 % — nejžádanější |
| TypeScript | 2× | 50.0 % — roste |
| CI/CD | 3× | 33.3 % |
| AWS | 3× | 0.0 % — čistý noise |

### 3.3 Role (20 %) — `role.py`

Detekuje, zda je role skutečně inženýrská nebo "fake engineer".

**ENGINEERING keywords (14):** engineer, integrator, architect, R&D, developer, technical lead...

**FAKE ENGINEER keywords (8):** customer service engineer, field service engineer, sales engineer, support engineer...

**Logika:**
```
eng_hits > 0 AND fake_hits == 0 → 80-100 (engineering role)
eng_hits > 0 AND fake_hits > 0 → max(10, 80 - fake_penalty)
fake_title + "engineer" in title → 15 (fake engineer pattern)
title_has_engineer + weak text → 60
fake_hits only → 20 (non-engineering)
no signal → 35
```

**Výskyt fake engineer patternu:** 3/24 nabídek (Konecranes #022 — Customer Service Engineer).

### 3.4 Growth (10 %) — `growth.py`

Hodnotí zaměstnavatele: strategický employer = kariérní růst.

| Kategorie | Score | Příklady |
|-----------|-------|----------|
| Strategic | 100 | Siemens, ABB, Bosch, Rockwell, Google, MS, Amazon |
| Growth | 60 | Atlas Copco, Fanuc, Kuka, Honeywell, SICK |
| Unknown | 20 | Ostatní |

**Proč jen 10 %:** I u ideálního employeru může být role mimo — doména a tech stack jsou důležitější.

### 3.5 Formal (5 %) — `formal.py`

Detekuje formální požadavky (degree) a flexibilitu.

**Degree keywords (10):** bachelor, master, phd, degree, university degree, titul, inženýr...
**Flexibility keywords (8):** equivalent practical experience, or comparable, don't meet every requirement...

**Logika:**
```
degree_hits > 0 AND flex_hits > 0 → 30-50 (degree required but flexible)
degree_hits > 0 AND flex_hits == 0 → 20 (degree required, no flexibility)
flex_hits > 0 AND degree_hits == 0 → 55 (no degree requirement)
no signal → 50
```

**Kalibrace:** Původně formal=10 %. Sníženo na 5 % po zjištění, že ~50 % employerů akceptuje "ekvivalentní praxi". Degree gap je mitigovatelný argumentací.

### 3.6 Location (5 %) — `location.py`

CZ-centric scoring. Praha/Brno/Ostrava = vysoké score, remote = bonus, distant = penalta.

| Pattern | Score |
|---------|-------|
| Strong remote (2+ hits) | 95 |
| Remote available (1 hit) | 80 |
| CZ location | 70 (office penalty -10 per hit) |
| Office-only | 35 |
| Distant CZ (Cheb, Karviná...) | max(5, 30 - distant×15) |
| No signal | 50 |

---

## 4. Kalibrační iterace — Jak váhy vznikly

Weights nebyly odhadnuty — byly **iterativně kalibrovány na reálných datech**:

### Iterace 0 — Ruční LLM analýza (bez kódu)
LLM v chatu dostal text nabídky + autorův profil → vrátil strukturovanou analýzu. Tento proces odhalil 6 klíčových dimenzí.

### Iterace 1 — První weights (teoretické)
```
domain=30, tech=25, role=20, growth=10, formal=10, location=5
```
Testováno na 5 follow leadech. Siemens #007 vyšel 75 %, Desoutter #003 65 %. 

### Iterace 2 — Domain zvýšena na 35 %
Analýza 24 nabídek: 67 % je nerelevantních. Zvýšení domain weight z 30→35 zabránilo falešně pozitivnímu hodnocení (Toloka #024 by při 30 % byla SLEDOVAT, ale je to AI data annotation — mimo industrial focus).

### Iterace 3 — Formal snížena na 5 %
Praxe ukázala, že "equivalent practical experience" je akceptováno u ~50 % employerů. Snížení formal weight z 10→5.

### Finální verze (v0.5.0 — v kódu)
```
domain=35, tech=25, role=20, growth=10, formal=5, location=5
Thresholds: 65/50/40
```

### Kalibrační zpětná vazba z reálných dat:

| Nabídka | Očekávané score | Kódem spočtené | Tolerance |
|---------|----------------|----------------|-----------|
| Siemens #007 | ~75 % | 82.0 % ✅ | ±10 % |
| Desoutter #003 | ~65 % | 72.0 % ✅ | ±12 % |
| Google #010 | ~50 % | 52.0 % ✅ | ±10 % |
| MSM GROUP #015 | ~48 % | 48.0 % ✅ | ±10 % |
| Apify #001 | ~38 % | 38.0 % ✅ | ±10 % |
| Thermo Fisher #014 | ~60 % | 60.0 % ✅ | ±10 % |

---

## 5. Thresholds — Proč 65/50/40?

Thresholdy vycházejí z kumulativní distribuce score na 24 nabídkách:

```
≥ 65 % → SLEDOVAT high  (Siemens 82 %, Desoutter 72 %)
    → Aplikovat ihned, high EROI

50-64 % → SLEDOVAT medium (Thermo Fisher 60 %, Google 52 %)
    → Sledovat, zvážit po skill gap closure

40-49 % → HRANIČNÍ  (Toloka #024: 46 %)
    → Aplikovat jen pokud nízké náklady

< 40 % → NESLEDOVAT  (Apify 38 %, zbytek pod 35 %)
    → Nealokovat čas
```

**Hranice 65 %** byla zvolena, protože pod ní klesá pravděpodobnost konverze pod 50 % (Google #010 = 52 % fit, 15-25 % P converze).

---

## 6. Skill Gap Analysis (TechMatch)

Každý skill v nabídce je klasifikován do 3 kategorií:

| Kategorie | Význam | Dopad na score |
|-----------|--------|----------------|
| **direct_match** | Autor skill ovládá a je v nabídce | Zvyšuje score |
| **partial_match** | Koncepčně blízko (např. CNC→PLC) | Mírně zvyšuje |
| **no_match** | Skill v nabídci, autor neovládá | Nesnižuje, ale je to gap |

Gapy se **neodečítají** od score. Místo toho:
1. Snižují `coverage_multiplier` (čím víc skillů v nabídce, tím těžší je dosáhnout vysokého coverage)
2. Jsou reportovány jako `skill_gaps` pro rozhodování o doučení

---

## 7. Mapa: KB artefakty ↔ kód

```
synteticky_report_analyza.md                 agregovany_report.md
       │                                            │
       │ golden rules, weights, thresholds           │ 24 actual analyses
       │ SNR analýza, LinkedIn precision             │ follow leads (007, 003, 010...)
       ▼                                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     config.py                                │
│  DIMENSION_WEIGHTS, THRESHOLDS, SKILL_MATRIX,               │
│  CORE_INDUSTRIAL_KEYWORDS, STRATEGIC_EMPLOYERS, ...         │
└──────────┬──────────────────┬──────────────────┬────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
     domain.py            tech.py            role.py
     (35 % domain)        (25 % tech)         (20 % role)
           │                  │                  │
           ▼                  ▼                  ▼
            ┌──────────────────────────────────┐
            │          scorer.py                │
            │  score_job(features) → EROIResult │
            └────────────────┬─────────────────┘
                             │
                             ▼
            ┌──────────────────────────────────┐
            │         kb_writer.py              │
            │  agregovany_report.md ← formát    │
            │  metadata_stacku.json ← struktura │
            │  git commit                       │
            └──────────────────────────────────┘
                             │
                             ▼
              metadata_stacku.json
              (strojově čitelná data:
               role, tech_stack, domain,
               formal_requirements,
               company, eroi)
```

---

## 8. Limity a předpoklady

| Limitace | Dopad | Mitigace |
|----------|-------|----------|
| CZ-only location keywords | Mimo-CZ nabídky = under-scored | Location scorer vychází z CZ trhu |
| Industrial skill bias | IT/software role = under-scored | Záměrné — autor hledá industrial |
| Žádný salary parsing | Chybí finanční dimenze EROI | Salary data jen u 4 % nabídek |
| LinkedIn text noise | False positives z footerů | Noise stripping v extractoru |
| Statické weights | Nereagují na změny trhu | Manuální rekalibrace po každých 5 nabídkách |

---

## 9. Jednovětý souhrn

> **EROI scoring je formalizace toho, co LLM dělal v chatu: šest dimenzí (domain 35 %, tech 25 %, role 20 %, growth 10 %, formal 5 %, location 5 %) se specifickými weighty kalibrovanými na 24 LinkedIn nabídkách, iterativně vyladěnými na precision-recall analýze proti 5 follow leads.**

---

*Dokument generován: 2026-07-07 | Zdroje: kód (config.py + 6 scorerů) + KB artefakty (agregovany_report.md, synteticky_report_analyza.md, metadata_stacku.json, linkedin_mcp_roadmap_v2.md)*
