# Marginální analýza: Multi-user EROI V2 vs. konkurenční LinkedIn MCP ekosystém

**Datum:** 2026-07-07 | **Autor:** Dev (na základě tržního průzkumu)
**Účel:** Ověřit, zda navržená V2 architektura dává smysl v kontextu celosvětového MCP trhu

---

## 1. Stav LinkedIn MCP ekosystému (Q3 2026)

Trh je **překvapivě přeplněný** na to, že MCP protokol existuje ~14 měsíců. Identifikováno 12+ aktivních open-source serverů + 5 komerčních řešení.

### 1.1 Open-source hráči (řazeno dle hvězd)

| Server | Stars | Jazyk | Nástrojů | Přístup | Focus |
|--------|-------|-------|----------|---------|-------|
| **stickerdaniel/linkedin-mcp-server** | **~2 600** ★ | Python | 13 | Patchright scraping | Profily, firmy, joby, zprávy |
| adhikasp/mcp-linkedin | ~200 ★ | Python | 5 | Neoficiální API | Feed, job search |
| SanthaKumar-K-2004/linkedin-mcp-zero | ~150 ★ | Python | 23 (34 s browser) | Patchright + API | Joby, CV matching, alerty |
| devag7/linkedin-mcp | ~50 ★ | TypeScript | 22 | Voyager API ze stránky | Profily, feed, messaging, writes |
| michaeltabet/hs-linkedin-mcp | ~20 ★ | TypeScript | 11 | CDP + reálný browser | ATS resolve, EasyApply |
| francisco-perez-sorrosal/linkedin-mcp | ~15 ★ | Python | 11 | HTTP scraping (bez browser) | Background scraping, SQLite |
| wlyonscat/server-mcp-linkedin | ~10 ★ | Python | 9 | Neoficiální API | Resume, cover letters |
| raaaaaif/linkedin-research-agent-mcp | ~5 ★ | Python | 14 | Fork stickerdaniel | Outreach research |
| **linkedin-mcp-custom (my)** | **0 ★** | Python | 3 | Patchright scraping | **EROI scoring saved jobs** |

### 1.2 Komerční / hosted řešení

| Produkt | Cena | Focus |
|---------|------|-------|
| Taplio MCP | ~$40/mo | Content posting (oficiální) |
| FirstTouch | $99/mo | Outreach s HubSpot atribucí |
| ConnectSafely | Paid | 60+ LinkedIn actions |
| Item 12 | Free/paid | CRM + MCP v jednom |
| Zapier LinkedIn MCP | Zapier plan | Workflow automation |
| Bright Data / Apify | Usage-based | Bulk data extraction |

### 1.3 Klíčové zjištění

**Žádný z 12+ serverů nemá strukturovaný scoring job fit.** Všichni umí:
- ✅ Vyhledat joby (public search, filtry)
- ✅ Přečíst detail jobu (title, company, description)
- ✅ Číst profily a firmy

Nikdo neumí:
- ❌ **Ohodnotit job proti osobnímu profilu** (váhy, skill matrix, doménová relevance)
- ❌ **Kalibrovat scoring podle CV**
- ❌ **Persistentní KB write-back s verzováním**

---

## 2. Marginální analýza V2 komponent

### 2.1 Config extrakce (F1) — ✅ DOPORUČUJI

| Aspekt | Hodnota |
|--------|---------|
| Náklady | 8-16h |
| Přínos | Umožní EROI reuse jako knihovnu |
| Konkurenční výhoda | Žádný jiný server nemá configurable scoring |
| Riziko | Nízké — čistý refactor, žádná změna logiky |
| **Verdikt** | **Dělat. Nejvyšší poměr value/effort.** |

EROI scoring je jediný skutečný diferenciátor oproti 12+ konkurentům. Config extrakce ho udělá znovupoužitelným → základ pro PyPI balíček.

### 2.2 Profile Registry (F2) — ❌ NEDOPORUČUJI (teď)

| Aspekt | Hodnota |
|--------|---------|
| Náklady | 8-16h |
| Přínos | Multi-user, ale není poptávka |
| Konkurenční výhoda | Žádná — nikdo multi-user neřeší |
| Riziko | Střední — zvyšuje ban risk na více účtech |
| **Verdikt** | **Odložit. Když bude >1 user, udělat jednodušeji.** |

**Problém:** LinkedIn scraping je per-account ban risk. Multi-user podpora znamená:
- Správa N profilů (každý s vlastním browser profilem)
- N-násobný ban risk
- Složitá správa session
- **Nikdo z 12+ konkurentů multi-user neřeší** — a to mají reálné uživatele

### 2.3 CV Parser (F3b) — ⚠️ ODLOŽIT (zjednodušit)

| Aspekt | Hodnota |
|--------|---------|
| Náklady | 16-24h |
| Přínos | Automatická kalibrace z CV |
| Konkurenční výhoda | Unikátní, ale linkedin-mcp-zero už má resume parsing |
| Riziko | Vysoké — kvalita parsingu, LLM náklady |
| **Verdikt** | **Nedělat custom parser. Místo: LLM-assisted one-time setup.** |

Místo složitého CV parseru udělat:
1. `calibrate_from_profile(profile_text: str)` — LLM dostane text profilu a vrátí calibration.json
2. Manuální override v calibration.json
3. Žádný regex-based custom parser

### 2.4 KB Writer parametrizace (F4) — ✅ DOPORUČUJI (zjednodušeně)

| Aspekt | Hodnota |
|--------|---------|
| Náklady | 2-4h (místo 4-8h) |
| Přínos | Configurable path, ale jednoduše |
| Konkurenční výhoda | Nikdo nemá KB write-back |
| **Verdikt** | **Dělat, ale lightweight. Ne verzovat podle profile_id.** |

### 2.5 ThreadPoolExecutor v analyze_saved_jobs (F0.4) — ✅ NUTNÉ

| Aspekt | Hodnota |
|--------|---------|
| Náklady | 1-2h |
| Přínos | Zabraňuje MCP timeoutu u 25+ jobů |
| **Verdikt** | **Povinné. P2 pravidlo z pitevní knihy.** |

---

## 3. Revidovaný plán (lean V2)

### Nové pořadí: F0 → F1 → F4 (light) → F3a (light) → publish → F3b? → F5

```
F0 — Pitevní prevence          2-4h     ✅ IHNED
  ├── ThreadPoolExecutor (P2)
  ├── --no-optional-locks (P3)
  ├── subprocess timeout 15s (P1)
  └── @auditable wrapper (P5)

F1 — Config extrakce           8-16h    ✅ JADRO
  ├── Config dataclass + JSON loader
  ├── load_config(profile_id) s merge
  ├── Scorery berou config parametrem
  └── Legacy regression testy

F4 — KB Writer parametrizace   2-4h     ✅ LEHCE
  ├── KB_PATH z ENV nebo parametru
  ├── --no-optional-locks
  └── subprocess timeout 15s

F3a — MCP tools upgrade        4-6h     ✅ MINIMAL
  ├── profile_id parametr do analyze_saved_jobs
  ├── --profile CLI argument
  └── EROI score v get_job_details

─── PUBLISH na PyPI a GitHub ───         📦 MILNÍK

F3b? — Calibrate tool          4-8h     ⏸️ ZVAZIT
  └── LLM-assisted one-time setup

F5 — Testy + dokumentace       6-10h    ✅ DOKONCENI

Celkem: 26-48h (původně 54-92h)
```

### Co VYPOUŠTÍME oproti původnímu plánu:

| Komponenta | Původně | Teď | Důvod |
|-----------|---------|-----|-------|
| Profile Registry (F2) | 8-16h | ❌ VYPNUTO | Multi-user není poptávka, zvyšuje ban risk |
| CRUD profily | 4h | ❌ VYPNUTO | Jednoduchý --profile parameter stačí |
| CV Parser (F3b) | 16-24h | ❌ VYPNUTO | LLM-assisted one-time setup místo regex parseru |
| Verzování reportů per profile | 4h | ❌ VYPNUTO | Single-user + ENV path stačí |

---

## 4. Business case: EROI jako knihovna (doporučený pivot)

### 4.1 Současný stav: closed-source single-user server
- 0 uživatelů (kromě autora)
- 0 GitHub stars
- 3 tools
- Hardcoded pro CNC/industrial

### 4.2 Navrhovaný stav: open-source EROI scoring knihovna

```
┌─────────────────────────────────────────────────────┐
│                 linkedin-eroi (PyPI)                 │
│  pip install linkedin-eroi                           │
│                                                     │
│  from linkedin_eroi import EROIScorer               │
│  from linkedin_eroi.config import load_config       │
│                                                     │
│  scorer = EROIScorer(config=load_config("profil"))  │
│  result = scorer.score_job(title, company, text)    │
├─────────────────────────────────────────────────────┤
│  → Použitelné v JAKÉMKOLIV LinkedIn MCP serveru     │
│  → Integrace: stickerdaniel, mcp-linkedin-zero, ... │
│  → Síťový efekt: čím více integrací, tím větší     │
│    community kolem EROI metodiky                    │
└─────────────────────────────────────────────────────┘
```

### 4.3 Síťový efekt

```
  linkedin-eroi (PyPI)
       │
       ├──→ linkedin-mcp-custom (Ondřejův server)
       │      3 tools + EROI scoring
       │
       ├──→ stickerdaniel/linkedin-mcp-server
       │      2.6K ★ uživatelů → mohou použít EROI
       │
       ├──→ linkedin-mcp-zero
       │      ~150 ★ → EROI jako add-on scoring
       │
       └──→ future: EROI standalone tool
              (bez LinkedIn scraping, jen scoring API)
```

**Klíčová insight:** Multi-user nepotřebujeme implementovat sami. Stačí aby EROI byla dostupná jako PyPI balíček → každý MCP server si ji může integrovat → EROI metodika se šíří bez našeho provozního úsilí.

---

## 5. Závěr a doporučení

### 5.1 Verdikt k V2 architektuře

| Kritérium | Skóre (1-10) | Poznámka |
|-----------|-------------|----------|
| Technická kvalita návrhu | 8/10 | Čistá architektura, dobré oddělení |
| Vhodnost pro MCP doménu | 6/10 | Multi-user je nad rámec potřeby |
| Konkurenční výhoda | 9/10 | EROI scoring je unikátní |
| Adekvátnost scope | 4/10 | **Předimenzované** — 2/3 komponent nevyužito |
| Riziko LinkedIn blokace | 6/10 | Multi-user = multi-account ban risk |
| **Celkem** | **6.6/10** | **Dobrá idea, špatný scope** |

### 5.2 Co dělat

1. **EROI extrahovat jako PyPI knihovnu** — to je skutečný produkt
2. **Server zjednodušit: F0 + F1 + light F4 + light F3a** — ~30h práce
3. **Publikovat na GitHub + PyPI** — získat community feedback
4. **EROI metodiku dokumentovat** — blog post, README, examples
5. **Integrovat do stickerdaniel serveru** jako plugin (proof of concept)

### 5.3 Co nedělat (teď)

1. ❌ Profile Registry (F2) — nikdo multi-user nechce
2. ❌ CV Parser (F3b) — LLM-assisted one-time setup stačí
3. ❌ Verzování reportů per profile
4. ❌ Multi-account browser management

### 5.4 Jedna věta

> **EROI scoring je jediný skutečný diferenciátor v přeplněném LinkedIn MCP trhu — místo multi-user platformy ho publikuj jako open-source knihovnu a nech community, ať si ho integruje sama.**

---

*Vytvořeno: 2026-07-07 | Na základě analýzy 12+ LinkedIn MCP serverů + komerčního trhu*
