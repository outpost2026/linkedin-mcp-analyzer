# Analýza: obscura → outpost2026/MCP-linkedin

**De novo analýza + korelace s dokumentem `transfer_znalosti_obscura_outpost2026.md`**
Datum: 2026-07-17 (aktualizováno po detailním průzkumu upstreamu)
Autor: cnc-tools (autonomní eval)

---

## 1. KDO JE SAMUEL SEIDEL A CO JE obscura?

### Zásadní korekce narativu

**samuelseidel/obscura** je **fork** projektu **h4ckf0r0day/obscura**. Samuel Seidel má ve svém forku **přesně 1 vlastní commit** (387c614 — "Add fetch POST and header options"). Zbylých 39 commitů jsou buď upstream commity (sync) nebo commity jiných contributorů (mnaza, SGavrl, BrandNewJimZhang, F0Rextasy, atd.).

| Metrika | h4ckf0r0day/obscura | samuelseidel/obscura |
|---------|---------------------|---------------------|
| Stars | 19 300 | 0 |
| Forks | 1 400 | 0 |
| Commits | 302 | 40 (z toho **1 Samuelův**) |
| Contributors | 8+ aktivních (mnaza, SGavrl, BrandNewJimZhang, h4ckf0r0day, IrishWhiskey, sicko7947, ...) | 0 (fork bez vlastních přispěvatelů) |
| Release | v0.1.10 (July 2026) | v0.1.1-landomo.1 (May 2026, 3 měsíce pozadu) |
| Docker | Ano (multi-stage, distroless/cc) | Ne |
| MCP server | Ano (`obscura mcp` s 11 nástroji) | Ne |
| AGENTS.md | Ano (151 řádků — AI agent guide) | Ne |
| Web | obscura.sh (s docs) + doc.obscura.sh | Ne |
| Stealth | Ano (curl-impersonate TLS fingerprinting) | Ne |
| Komercializace | Obscura Cloud (waitlist), 4 proxy sponsor dealy | Nic |

Samuel Seidel je český solo vývojář který:
- Forknul obscura 27.4.2026 (v rané fázi upstreamu, ~v0.1.0)
- Přidal **1 feature**: `fetch` POST/header options pro landomo-canada-realtor
- Release `v0.1.1-landomo.1` používá výhradně pro svůj realitní projekt
- Nepřispívá zpět do upstreamu (0 PRů)

**Pro srovnání:** Upstream h4ckf0r0day/obscura je profesionální open-source projekt s obchodním modelem (Obscura Cloud + proxy affiliate), aktivní komunitou, pravidelnými releasy a vestavěným MCP serverem. Samuelův fork je personal branch pro specifický use case.

---

## 2. VALIDITA DOKUMENTU `transfer_znalosti_obscura_outpost2026.md`

### Kvalita: 8/10 (obsahově), 5/10 (sémanticky)

**Silné stránky:**
- Architektonická analýza kódu (sekce 2.2 A-P) je **fakticky správná** a detailní
- 12 transfer patternů (sekce 4) jsou solidní engineering principles
- Cross-domain mapování (sekce 3.1) je relevantní
- Risk assessment (sekce 8) je realistický
- Roadmap (sekce 6) je dobře strukturovaná

**Slabé stránky:**
- **Systematicky prezentuje obscura jako "Samuel Seidelův Rust projekt"** místo "fork h4ckf0r0day/obscura s pár commity". To je sémantická chyba — snižuje to důvěryhodnost zbytku analýzy.
- Dokument tvrdí *"repozitářová metadata: 0 hvězd, 0 forků, fork z h4ckf0r0day/obscura, síť 1394 forks celého projektu"* (ř.45) — přiznává fork, ale dále o projektu mluví jako o Samuelově vlastním díle
- Chybí zmínka, že upstream už má **MCP server** (`obscura mcp` s nástroji browser_navigate, browser_snapshot, browser_click atd.) — to je přímo relevantní pro tvůj projekt
- Kontext v sekci 0 (ř.13) říká *"projekt samuelseidel/obscura je open-source (Apache-2.0) headless browser napsaný v Rustu"* — technicky pravda, ale implikuje autorství
- 5 z 12 patternů (sekce 4) jsou generické softwarové patterny (workspace monorepo, feature flag, SSRF prevence, multi-platform release, právní compliance) — ne specificky z obscura

**Závěr k validitě:** Principy přenosu jsou **validní**, ale prezentační rámec je **zavádějící**. Hodnota analýzy je v architektonických patternech, ne v tom, že by Samuel Seidel byl expert, od kterého se máš učit.

---

## 3. DE NOVO ANALÝZA: Architektura obscura

(Čistě z kódu, bez vlivu transfer dokumentu)

### 3.1 OPRAVDU IMPRESIVNÍ VĚCI

#### A. Chrome DevTools Protocol implementace
obscura implementuje CDP na úrovni, která umožňuje drop-in replacement za headless Chrome pro Puppeteer i Playwright. To je **extrémně náročná engineering práce** (~27KB server.rs, 12 domain modulů). Tvůj MCP server je srovnatelný v tom, že oba implementují protokol → handler → response pattern.

#### B. Jediná binárka, žádné dependency
70 MB binárka, 30 MB RAM, instant start. Žádný Chrome, Node.js, Python runtime. To je pro AI agenty zásadní — tvůj Python MCP server s Playwrightem má cold start ~5-10s + 200+ MB RAM.

#### C. Worker process isolation
Parent/worker architektura přes JSON-RPC na pipe — **to je přímo relevantní pro tvoje per-portál scrapování**. Každý worker v izolovaném procesu, crash-safe, round-robin load balancing.

### 3.2 TVŮJ MCP-LINKEDIN VS OBSCURA MCP

obscura v0.1.10 už má **vestavěný MCP server** (`obscura mcp`):

| Tool | obscura MCP | linkedin-mcp-custom |
|------|------------|---------------------|
| browser_navigate | ✅ | ✅ (přes patchright) |
| browser_snapshot | ✅ | ✅ (extractor) |
| browser_click | ✅ | ❌ |
| browser_fill/type | ✅ | ❌ |
| browser_evaluate | ✅ | ❌ |
| browser_network_requests | ✅ | ✅ (RequestTrace) |
| EROI scoring | ❌ | ✅ (unikátní) |
| KB write-back | ❌ | ✅ (unikátní) |
| Synthetic report | ❌ | ✅ (unikátní) |

**Průnik:** ~40% MCP nástrojů se překrývá. **Tvoje EROI scoring + KB write-back** je unikátní hodnota, kterou obscura nemá.

### 3.3 CO CHYBÍ V DOKUMENTU (čistě můj nález)

1. **obscura už má MCP server** — transfer dokument to nezmiňuje, přitom je to nejrelevantnější část
2. **Upstream má 19.3k hvězd, ne 0** — hardcore komunita, přispěvatelé z celého světa
3. **Samuelův fork je za upstreamem** — v0.1.1 vs v0.1.10, chybí mu:
   - MCP server
   - SSR detection (Accessibility domain)
   - IO streaming
   - Docker image
   - `--output` flag pro fetch
   - Script execution budget (`OBSCURA_SCRIPT_DEADLINE_MS`)
4. **Stealth není feature flag v Cargo.toml** — je to `curl-impersonate` based TLS fingerprinting. Transfer dokument to popisuje správně
5. **V8 embedding** — obscura embeduje V8 přímo (přes deno_core), ne jako subprocess. To dává 85ms page load

---

## 4. SNR (SIGNAL-TO-NOISE) ANALÝZA

### Signál (hodnota pro MCP-linkedin)

| Pattern | SNR | Akce |
|---------|-----|------|
| **Worker process isolation (JSON-RPC pipe)** | 🔥 Vysoký | Implementovat pro per-portál scrapování |
| **CDP-style dispatcher tabulka** | 🔥 Vysoký | Refaktorovat dispatcher v MCP serveru |
| **Fast-path no-op responses** | 🔥 Vysoký | Přidat do linkedin-mcp (tools/list, resources/list) |
| **BrowserContext/ScraperContext Arc pattern** | 🔥 Vysoký | Zapouzdřit LinkedIn session do Context |
| **SSRF prevence (validate_url)** | 📈 Střední | Přidat do fetch/extract toolů |
| **RequestInterceptor middleware** | 📈 Střední | Rate limiter + audit |
| **Feature flag pro stealth** | 📈 Střední | `linkedin-mcp[stealth]` |
| **Workspace monorepo** | 📉 Nízký | Předčasné – máš 2 nástroje |
| **RobotsCache** | 📉 Nízký | Pro LinkedIn API irelevantní |
| **Multi-platform release** | 📉 Nízký | Pro teď zbytečné |

### Šum (v dokumentu nadhodnoceno)

- **"Samuel Seidel je český solo vývojář"** — relevantní jen jako kontext, ne jako autorita
- **5 z 12 patternů jsou generické** — ne specificky z obscura
- **134KB bootstrap.js jako anti-pattern** — každý headless browser má DOM API knihovnu
- **Vlastní encoder na CPU** — zmínka z FB příspěvku, není v repu
- **landomo-canada-realtor architektura** — relevantní, ale není to obscura

### Celkové SNR: ~65%

Z 999 řádků je ~650 řádků čistého signálu. Zbylých ~350 řádků tvoří: kognitivní framework (50), roadmap (100), anti-patterns (50), reference (50), appendix (100).

---

## 5. DOPORUČENÍ PRO MCP-LINKEDIN

### OKAMŽITĚ (tento týden)

1. **Přidej `validate_url` SSRF guard** do fetch/extract toolů (transfer dokument sekce 7.1)
   ```python
   def validate_url(url: str) -> None:
       if parsed.scheme not in {"http", "https"}:
           raise SSRFError(...)
   ```

2. **Přidej fast-path no-op responses** do serveru:
   ```python
   MCP_NOOP_METHODS = {"prompts/list": {"prompts": []}, "resources/list": {"resources": []}}
   ```

3. **Extrahuj RequestTrace pattern** z MCP-Jobs do linkedin-mcp-custom

### KRÁTKODOBĚ (2-3 týdny)

4. **Refaktoruj na Context pattern**:
   ```python
   @dataclass
   class LinkedInContext:
       cookies: CookieJar
       http_client: httpx.AsyncClient
       rate_limiter: AsyncLimiter
       browser: Browser
   ```

5. **Middleware pipeline** pro auth, rate limit, audit

### KDYŽ SE ROZHODNEŠ PRO PER-PORTÁL SCRAPING

6. **Worker process isolation** — přesně podle patternu z obscura:
   - Parent: dispatcher (round-robin)
   - Workers: pipe JSON-RPC
   - Crash-safe: respawn na crash

---

## 6. FINÁLNÍ VERDIKT

### Dokument `transfer_znalosti_obscura_outpost2026.md`

| Kritérium | Hodnocení |
|-----------|-----------|
| Faktická správnost | ✅ 95% (architektura kódu je správně) |
| Sémantická validita | ⚠️ 50% (prezentuje fork jako vlastní projekt) |
| Přenositelnost patternů | ✅ 80% (12 patternů, z toho 7 unikátních) |
| Hloubka analýzy | ✅ 85% (sekce 2.2 A-P je detailní) |
| Praktická použitelnost | ✅ 75% (roadmap + konkrétní TODO) |
| Objektivita | ❌ 40% (autorství Samuela Seidela nadhodnoceno) |

### Má cenu obscura sledovat?

1. **Sleduj h4ckf0r0day/obscura**, ne samuelseidel/obscura — upstream má 19.3k hvězd, aktivní komunitu, pravidelné release, vestavěný MCP server
2. **Samuel Seidel není relevantní autorita pro obscura** — ale jeho další projekty (landomo-canada-realtor, eu-ai-act-legal-rag) možná ano
3. **Přenositelné patterny z obscura jsou reálné** — worker isolation, CDP dispatcher, BrowserContext, fast-path responses
4. **Tvé EROI scoring + KB write-back je unikátní** — obscura MCP server nemá nic podobného

### Akce

- Zachovej transfer dokument jako referenci (architektonické patterny jsou validní)
- Sleduj místo samuelseidel/obscura raději h4ckf0r0day/obscura
- Implementuj top 3 patterny (validate_url, fast-path, RequestTrace) tento týden
- Worker isolation pattern si ulož do backlogu pro per-portál scraping

---

*Konec analýzy. 2026-07-17.*
