# PITEVNÍ KNIHA: LINKEDIN MCP PIPELINE

## ZÁZNAM 001: Typová záměna BrowserContext vs. Browser (False is_connected)

* **Symptom:** `AttributeError: 'BrowserContext' object has no attribute 'is_connected'` při opakovaném volání `get_saved_jobs`.
* **Příčina:** `get_or_create_browser()` používala `launch_persistent_context()`, která vrací `BrowserContext`, nikoliv `Browser`. Návratová hodnota byla uložena do proměnné `_browser` (typově anotované jako `Browser`). Kontrola `_browser.is_connected()` selhala, protože `BrowserContext` tuto metodu nemá. Funkce `get_or_create_browser()` ani `get_page()` neměly `_context` deklarovaný jako `global`.
* **Fyzikální realita:** Patchright/Playwright API striktně odděluje `Browser` (proces chromu) a `BrowserContext` (izolovaný session kontext s cookies). Každá metoda patří jiné třídě. Python přiřadil objekt do proměnné se špatným typem — interpret nehlídá typy, jen existenci atributů.
* **Korekce (Pravidlo):** `_browser` proměnná odstraněna. `get_or_create_browser()` pracuje výhradně s `_context: BrowserContext`. Re-use kontroluje stav stránky `pages[0].is_closed()` místo neexistující `_context.is_connected()`. Globální proměnné deklarovat explicitně: `global _context, _page, _playwright`.

## ZÁZNAM 002: Stínová lokální proměnná _page (Missing global)

* **Symptom:** `AssertionError` v `get_page()` — `assert _page is not None` selhal, přestože `get_or_create_browser()` právě doběhl.
* **Příčina:** V `get_or_create_browser()` byl proveden zápis `_page = pages[0]`, ale `_page` nebyl deklarován jako `global`. Python vytvořil novou lokální proměnnou uvnitř funkce namísto modifikace modulové singleton proměnné. Globální `_page` zůstala `None`.
* **Fyzikální realita:** Python striktně odděluje lokální a globální scope. Zápis do proměnné bez `global` deklarace = nová lokální proměnná. Čtení bez `global` = čtení z globálního scope (funkční). Kombinace čtení+zápisu bez `global` = `UnboundLocalError`; samotný zápis bez `global` = tichá lokální shadowing.
* **Korekce (Pravidlo):** Každá funkce, která provádí **zápis** do modulové globální proměnné, musí mít explicitní `global jméno_proměnné`. Inspekce: `grep -n "global\|^_\(context\|page\|playwright\) =" browser.py`.

## ZÁZNAM 003: Auth navigační konflikt (is_logged_in přesměrování)

* **Symptom:** `scrape_saved_jobs()` vracela prázdný seznam `job_ids: []`, přestože LinkedIn účet měl >10 saved jobs. Debug skript s přímým `page.goto()` + extrakcí našel 17 jobů.
* **Příčina:** `extract_page()` volala `ensure_authenticated()` **po** navigaci na cílovou URL (`/jobs-tracker/`). `ensure_authenticated()` → `is_logged_in()` → `page.goto('https://www.linkedin.com/feed/')`. Tím přesměrovala stránku na feed. Následné `_extract_job_ids()` běželo na `/feed/`, kde nejsou žádné job linky.
* **Fyzikální realita:** `is_logged_in()` není read-only check. Aby ověřila přihlášení, fyzicky naviguje prohlížeč na feed LinkedIn. Tato navigace je destruktivní — přepisuje aktuální URL a DOM. Volání `ensure_authenticated()` po navigaci = zahození target stránky.
* **Korekce (Pravidlo):** Auth check musí vždy předcházet navigaci na target URL. Pořadí: `ensure_authenticated()` → `navigate_to_page()`. V MCP tool `_get_extractor()` je auth volán dvakrát (jednou v helperu, jednou v `extract_page`) — redundantní ale neškodné, pokud je první volání před navigací.

## ZÁZNAM 004: Fragilita CSS selektorů (LinkedIn DOM mutace)

* **Symptom:** `_extract_job_metadata()` vracela prázdné `{title: '', company: '', location: ''}`, i když job detail page obsahoval všechna data.
* **Příčina:** Metoda používala hardcoded CSS třídy: `.job-details-jobs-unified-top-card__job-title`, `.jobs-unified-top-card__company-name`, `.jobs-unified-top-card__bullet`. LinkedIn generuje CSS třídy dynamicky a mění je bez varování. V aktuální verzi DOMu nebyl `<h1>`, title byl v `<p>` s auto-generated třídou `e6590096 _3293afb7 _3ff84621...`.
* **Fyzikální realita:** LinkedIn je SPA (Single Page Application) s kontinuálním A/B testováním CSS tříd. Statické selektory mají životnost týdny až měsíce. Jediný stabilní identifikátor je `a[href*="/company/"]` pro firmu — protože company page URL struktura se nemění.
* **Korekce (Pravidlo):** Text-based parsing z `main.innerText`. Firma z `a[href*="/company/"]`, title z prvního bloku textu, který není jméno firmy, lokace z bloku obsahujícího pattern města (`/Praha/i`, `/Brno/i`, `/Česko/i`). Žádné CSS třídy v selektorech — pouze sémantické HTML elementy (`main`, `a[href*="/company/"]`).

## ZÁZNAM 005: Paginační slepota (Missing second page)

* **Symptom:** `scrape_saved_jobs()` vracela 10 job IDs, přestože účet měl 17 saved jobs.
* **Příčina:** LinkedIn jobs-tracker zobrazuje prvních 10 výsledků na stránce `/jobs-tracker/`. Dalších 7 je na straně 2, dostupné přes paginaci. `scrape_saved_jobs()` scrapovala pouze první stranu bez detekce nebo kliknutí na tlačítko "Další".
* **Fyzikální realita:** LinkedIn používá klientskou paginaci s číslovanými tlačítky (1, 2, 3...) a "Další" dole na stránce. CSS třídy paginačních elementů jsou auto-generated a nemají stabilní selektor. Po kliknutí na číslo 2 se URL změní na `/jobs-tracker/?stage=saved`.
* **Korekce (Pravidlo):** Heuristická detekce paginace: vyhledat všechny viditelné `span`/`button`/`a` elementy s textem odpovídajícím číslu stránky (`^\d+$`) nebo "Další"/"Next". Seřadit podle vertikální pozice, kliknout na nejnižší (strana 2 nebo Další). Opakovat max 5× nebo dokud nepřibývají nové job ID.

## ZÁZNAM 006: Špatný git repo root v KBWriter (parents[2] → parents[1])

* **Symptom:** `KBWriter.commit_changes()` logoval `Git commit failed: fatal: not a git repository`, přestože `B2B-Knowledge-Base` je validní git repo.
* **Příčina:** `commit_changes()` počítala repo root jako `self.linkedin_dir.parents[2]`. Cesta: `C:/.../B2B-Knowledge-Base/02_ANALÝZY/00_linkedin`. `parents[0]` = `02_ANALÝZY`, `parents[1]` = `B2B-Knowledge-Base`, `parents[2]` = `_github`. Index 2 mířil o úroveň výš, do adresáře obsahujícího všechny repa, který není git repo.
* **Fyzikální realita:** `Path.parents` je 0-indexovaný od nejbližšího rodiče. Chyba o 1 v indexu = rozdíl mezi validním repem a nesmyslným adresářem. `subprocess.run` selže tichým `CalledProcessError`, protože cwd není git repo.
* **Korekce (Pravidlo):** `parents[1]` pro repo root při hloubce linkedin_dir = 2 od repo root. Verifikace: `print(self.linkedin_dir.relative_to(repo_root))` před prvním commitem.

---

---

## DIAGNOSTICKÝ FILTR PRO LINKEDIN MCP

**A — Browser vrstva (browser.py)**
1. Jsou všechny globální proměnné deklarovány v každé funkci, která do nich zapisuje? (001, 002)
2. Je `_context` používáno místo `_browser` pro persistent context? (001)
3. Je `_page` nastaveno po `get_or_create_browser()`? (002)
4. Je `close_browser` zbaveno referencí na `_browser`? (001)

**B — Scraping vrstva (extractor.py)**
5. Volá se `ensure_authenticated()` PŘED `navigate_to_page()`, ne po? (003)
6. Neobsahují metadata selektory hardcoded CSS třídy? (004)
7. Je firma extrahována z `a[href*="/company/"]`? (004)
8. Je title extrahován text-based parsingem z `main.innerText`? (004)
9. Je lokace extrahována pattern matchingem na city/region? (004)
10. Probíhá paginace s heuristickým klikáním na "Další" / číslo stránky? (005)
11. Jsou job ID extrahovány z `a[href*="/jobs/view/"]`? (005)

**C — KB Writer vrstva (kb_writer.py)**
12. Je repo root počítán jako `self.linkedin_dir.parents[1]`? (006)
13. Je `subprocess.run` volán s `cwd=repo_root`? (006)
14. Je `parents` index verifikován před prvním produkčním write? (006)
15. Existuje v souboru právě jedna definice `write_all()`? (009)
16. Je `commit_changes()` definovaná jako samostatná metoda na úrovni třídy? (009)
17. Nenásleduje dead code za `return` uvnitř metody? (009)

**D — Konfigurační vrstva (config.py)**
18. Je SKILL_MATRIX synchronizovaný s aktuálním CV? (010)
19. Jsou nové kompetence (MCP, FastMCP, agentic systems, DevSecOps) přidány do matice? (010)

**E — Matching vrstva (domain.py, location.py, analysis/__init__.py)**
20. Volá se `strip_diacritics()` před `lower()` v každém matching helperu? (008)
21. Používá dedup normalizace `strip_diacritics()` + `lower()` + collapse whitespace? (008)
22. Je `strip_diacritics()` definovaná centrálně v `analysis/__init__.py`? (008)

## ZÁZNAM 007: Paginační tvrdokód (parseInt(p.text) === 2)

* **Symptom:** `scrape_saved_jobs()` vracela pouze 20 job IDs z 27 uložených. Page 3+ nikdy nebyly scrapovány.
* **Příčina:** `_click_next_page()` v `extractor.py` obsahovala `parseInt(p.text) === 2` — tvrdokód na číslo stránky 2. JavaScript Array.from → filter porovnával text každého paginačního tlačítka s konstantou `2`. Page 3, 4, 5 nikdy neprošly filtrem.
* **Fyzikální realita:** `===` v JavaScriptu je strict equality — `3 === 2` je `false`, `4 === 2` je `false`. Žádná magická konverze. Konstantní hodnota v extrakční logice znamená, že se vždy extrahovala jen page 2 (druhá stránka), další stránky byly ignorovány.
* **Korekce (Pravidlo):** `_click_next_page()` nyní přijímá parametr `current_page: int`. JavaScript filter používá `=== current_page + 1`. Volání ze smyčky `scrape_saved_jobs` předává `page_num` (2, 3, 4, 5). Žádné konstanty v extrakční logice — hodnoty vždy parametrizované z volající funkce.

## ZÁZNAM 008: Diakritická slepota (TECHNICKÝ ≠ TECHNICKY)

* **Symptom:** Dedup falsely detekoval nový záznam místo updatu stávajícího u jobů obsahujících české názvy (např. "TECHNICKÝ PRACOVNÍK" vs "TECHNICKY PRACOVNIK"). Scoring vracel nižší match, protože diakritická varianta neodpovídala ASCII keywordům.
* **Příčina:** `_count_matches()` v `domain.py`, `location_score()` v `location.py` a `_normalize()` v `kb_writer.py` prováděly `text.lower()` bez odstranění diakritiky. "TECHNICKÝ" se neshodoval s "technicky" v keyword listu. Dedup porovnával "technický pracovník|siemens" s "technicky pracovnik|siemens" — false mismatch.
* **Fyzikální realita:** `str.lower()` neodstraňuje diakritiku — mění jen velikost písmen. Čeština používá háčky a čárky (ˇ´˚¨), které ASCII keyword list neobsahuje. NFKD normalizace + ASCII ignore decode je jediný spolehlivý způsob, jak "TECHNICKÝ" → "TECHNICKY" bez nutnosti ručního mapování.
* **Korekce (Pravidlo):** Sdílená `strip_diacritics()` v `analysis/__init__.py`: `unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")`. Volána před každým `lower()` v matching logice. Dedup normalizace prochází `_util_normalize()` → `strip_diacritics()` + `lower()` + collapse whitespace.

## ZÁZNAM 009: Ghost write_all (duplicitní metoda + dead code)

* **Symptom:** `test_write_all_no_commit` failoval s `AttributeError: 'KBWriter' object has no attribute 'commit_changes'`, přestože `commit_changes()` byla v souboru definovaná.
* **Příčina:** V `kb_writer.py` existovaly DVĚ metody `write_all()`. První (nová verze s dedup) volala `self.commit_changes()` na řádku 361. Druhá (stará verze, řádek 389) překrývala první. Python použil druhou definici (ta vyhrává v MRO). Uvnitř první `write_all()` byl dead code blok (řádky 370-387) který vypadal jako metoda `commit_changes()` ale byl odsazený jako součást `write_all()` a následoval za `return` — nikdy se neprovedl. Linter nevaroval, test selhal.
* **Fyzikální realita:** Python class body se vykoná sekvenčně. Druhá definice `write_all` přepíše první v `__dict__` třídy. Dead code mezi `return` a koncem metody je syntakticky validní, sémanticky nedosažitelný — Python ho nehlásí jako chybu. IDE a statická analýza obvykle varují, ale ne vždy (záleží na konfiguraci linteru).
* **Korekce (Pravidlo):** Smazána druhá `write_all()`. Dead code extrahován do proper metody `commit_changes(self, message=None)` na úrovni třídy. Verifikace: `grep -n "def write_all\|def commit_changes" kb_writer.py` — každá metoda právě jednou, na správné indentaci.

## ZÁZNAM 010: Skill matrix divergence (CV 2026-07 vs config.py)

* **Symptom:** EROI scoring neodměňoval MCP-related dovednosti, přestože CV obsahuje "MCP server design", "FastMCP", "agentic systems", "cross-repo search" atd. Skill gap report ukazoval "no_match" u skillů, které autor reálně ovládá.
* **Příčina:** `SKILL_MATRIX` v `config.py` nebyl aktualizován od nasazení MCP pipeline (Fáze 3). Nové kompetence z CV 2026-07 (MCP ekosystém, DevSecOps, bus-factor zero metodologie) v matici chyběly. Scoring engine je pasivní — hodnotí pouze to, co je v konfiguraci.
* **Fyzikální realita:** EROI engine není ML model, který by extrahoval nové koncepty. Je to deterministic keyword matching engine — bez definice skillu v matici je vždy "no_match". SKILL_MATRIX je ručně udržovaný artifact, který musí reflektovat aktuální CV. Bez pravidelné synchronizace scoring degraduje.
* **Korekce (Pravidlo):** Přidáno 16 položek do SKILL_MATRIX (MCP, FastMCP, agentic systems, multi-agent, tool registry, cross-repo search, session state, GitHub Actions, DevSecOps, CodeQL, Dependabot, matrix testing, bus factor, bus-factor zero). Přidáno "bus factor" a "bus-factor zero" do ENGINEERING_ROLE_KEYWORDS. Next: proces pravidelné sync CV→SKILL_MATRIX každý kvartál.

---

## ZÁZNAM 011: Paginační target_page+1 (přeskakování stránek)

* **Symptom:** `scrape_saved_jobs()` vracela 17 job IDs z 27 při spuštění přes MCP tool (přes CLI všech 27). Stránka 2 a 3 nebyly scrapovány, přestože `_click_next_page()` vracela `True`.
* **Příčina:** `_click_next_page(current_page=2)` počítala `target_page = current_page + 1 = 3`. Hledala tedy tlačítko s číslem 3 a klikala na něj. Stránka 2 byla přeskočena. Na page 3 (která neexistuje nebo má stejná doporučená ID) loop skončil. Zdánlivě paginace fungovala (vrátila True), ale reálně skákala přes stránky.
* **Slepá ulička:** První fix přidal `wait_for_selector('ul[class*="jobs"] a[href*="/jobs/view/"]')` — nepomohlo, protože selektor cílený na main job list neexistuje (jobs nejsou `<a>` elementy). Druhý fix odstranil `new_ids` dedup check (dedup až na konec) — pomohlo částečně (27 ID přes CLI), ale přes MPC pořád 17.
* **Fyzikální realita:** Parametr `page_num` začínal na 2 (první iterace = page 2). `target_page = current_page + 1` přidal další +1. Výsledek: `_click_next_page(2)` hledá page 3 místo page 2. Tento bug vznikl při refactoringu v Session 2 (Záznam 007), kde byl tvrdokód `=== 2` nahrazen dynamickým `=== current_page` — ale s chybným +1 na špatném místě.
* **Korekce (Pravidlo):** Celá metoda přepsána na bezparametrovou `_click_next_page()`. Místo hledání čísel stránek hledá výhradně tlačítko "Další"/"Next" (CSS selector + text fallback). Žádná aritmetika s page numbers. Loop v `scrape_saved_jobs()` používá `for _ in range(2, 6)` — nezávisle na page numbers.

## ZÁZNAM 012: Slepá ulička — clicking approach pro job ID extrakci

* **Symptom:** Metoda `_extract_job_ids_by_clicking()` — 120 řádků kódu, 3 pokusy o implementaci. Nikdy nedošla do produkce.
* **Příčina:** LinkedIn tracker page neukládá job ID hlavního seznamu do DOM atributů. Job karty používají React state / JS click handlery. Pokus: kliknout na každou kartu, počkat na navigaci na `/jobs/view/ID`, přečíst URL, vrátit se zpět. Implementace selhala na:
  * `f-string` s `{text!r}` pro Python → JS — nekonzistentní escaping
  * `page.evaluate` vrací `Any` → Python neví, že `info['href']` je string → `.match()` není metoda stringu → LSP error
  * Click na kartu ne vždy spustí navigaci (někdy otevře side panel, ne novou URL)
  * Go_back po navigaci ztrácí scroll pozici a stav paginace
* **Fyzikální realita:** Clicking-based extrakce je O(n) requestů navíc, kde n = počet jobů. Každý click → wait → read URL → go_back trvá ~5s. Pro 27 jobů = 135s jen na extrakci ID. To je neúměrné, zvlášť když pipeline pak stejně scrapuje každý job zvlášť. Principiálně správný nápad, prakticky nepoužitelný.
* **Korekce (Pravidlo):** Metoda smazána. ID extrakce řešena výhradně přes full outerHTML scan + script JSON bloky + všechny DOM atributy. Pokud LinkedIn změní strukturu tak, že ID nebudou v outerHTML, použít API intercept místo DOM klikání.

## ZÁZNAM 013: Job ID nejsou v DOM hlavního seznamu (trapped in React state)

* **Symptom:** `_extract_job_ids()` vracela stále stejných 17 ID bez ohledu na stránku, přestože innerText na page 2 ukazoval 7 jiných jobů. 5 různých strategií extrakce selhalo.
* **Příčina:** Postupně testováno: (1) `a[href*="/jobs/view/"]` → 17 ID z doporučených/sidebar jobů. (2) data-* atributy → 0 nových. (3) onclick/onmousedown → 0. (4) `document.querySelectorAll('*')` loop všech atributů → pořád stejných 17. (5) Script JSON bloby s 10-číselnými patterny → konečně 27 ID.
* **Slepá ulička:** Mezi strategií 4 a 5 bylo 6 neúspěšných pokusů včetně:
  * Hledání `urn:li:jobPosting:ID` v atributech → nikde
  * `entityUrn` pattern → nikde
  * 10-digit numbers s kontextem `job|tracker|saved` → občas falešné pozitivy (tracking ID)
  * Regex context check na 30→50→100 znaků kolem čísla
* **Fyzikální realita:** Job ID prvních 17 jobů jsou v "doporučené/similar jobs" sekci jako `<a href="/jobs/view/ID">`. Zbylých 10 je pouze v React state, serializovaném do `<script>` tagu jako `jobPosting:4435589028` atd. Bez script JSON scanningu jsou tato ID neviditelná.
* **Korekce (Pravidlo):** `_extract_job_ids()` kombinuje 4 strategie v jednom evaluate: (1) `<a href>` — rychlý sběr, (2) všechny atributy všech elementů — pokrytí data-*, (3) script JSON 10-digit numbers s job kontextem — hlavní zdroj pro page 2+, (4) `document.documentElement.outerHTML` regex — záchytná síť. Vše v jednom JS evaluate (1 DOM průchod místo 4).

## ZÁZNAM 014: Pipeline timeout přes MCP (vs CLI)

* **Symptom:** `analyze_saved_jobs` MCP tool vracel `MCP error -32001: Request timed out`. Stejný kód spuštěný z CLI jako `uv run python -c "..."` doběhl kompletně za ~120s (27 jobů).
* **Příčina:** MCP protokol má implicitní timeout (default ~60s). `analyze_saved_jobs` scrapuje každý job sekvenčně: paginace (3 page turns) + navigate_to_page + scroll + extract_inner_text. Každý job ~5s. 27 jobů × 5s = 135s. Browser overhead + KB writer git commit přidává dalších ~15s. Celkem ~150s — 2.5× nad MCP timeout.
* **Slepá ulička:** Zvýšení timeoutu na straně FastMCP serveru není možné bez úpravy `server.py` a restartu serveru. Limit je na straně MCP klienta (hostitele).
* **Fyzikální realita:** MCP tool timeout je vlastnost protokolu, ne Python exception. FastMCP default timeout je 60s pro tool execution. Řešení:
  1. **Snížit počet jobů na dávku** — parametr `max_jobs=5` by zkrátil dobu na ~30s
  2. **Paralelní scrapování** — `asyncio.gather` by zpracovalo 5 jobů najednou → 27/5 × 5s = ~30s
  3. **CLI run** — přímé volání z command line nemá MCP timeout limit
* **Korekce (Pravidlo):** Přidán parametr `max_jobs: int = 0` (0 = všechny) do `analyze_saved_jobs`. Pipeline lze volat po dávkách. Pro plný běh používat CLI skript místo MCP toolu.

## ZÁZNAM 015: KBWriter dedup fallback broken (company.industry = None)

* **Symptom:** Fallback dedup v `_find_entry_index()` nikdy nenajde shodu podle title+company, přestože stejný job existuje v metadatech.
* **Příčina:** Porovnání: `_normalize(f"{eroi.job_title}|{eroi.company}")` vs `_normalize(f"{entry.get('title', '')}|{entry.get('company', {}).get('industry', '')}")`. `company` struktura v metadatech je `{"type": None, "size_range": None, "industry": None}`. `.get('industry', '')` vrací `None` (nebo prázdno) → vždy `_normalize("sometitle|")` vs `_normalize("sometitle|siemens")` → nikdy se neshoduje.
* **Fyzikální realita:** Kód vznikl splitem původní `company` string (např. "Siemens") na strukturovaný objekt `{"type": None, "size_range": None, "industry": None}` během refactoringu. Někdo zapomněl aktualizovat dedup porovnání. Bug je tichý — nepadá, jen občas vytvoří duplicitní záznam místo updatu.
* **Korekce (Pravidlo):** Nahradit `entry.get('company', {}).get('industry', '')` za `str(entry.get('company', {}))` nebo lépe přidat `company_name` field do metadata JSON. Nebo použít přímo `entry.get('title', '')` a porovnávat jen title (company je v title+company dedup redundantní).

## ZÁZNAM 016: Paginační loop early dedup break (ztracená ID z pages 2+)

* **Symptom:** `scrape_saved_jobs()` po opravě paginace (Záznam 011) stále vracela jen 17 ID při běhu přes MCP (přes CLI 27). Early dedup break přerušil loop.
* **Příčina:** Původní logika: `new_ids = [jid for jid in more_ids if jid not in all_job_ids]; if not new_ids: break`. Na page 2 `_extract_job_ids()` vrací stejná ID z doporučených jobů (která už jsou v `all_job_ids` z page 1). `new_ids` je prázdný → break → page 2 text je scrapován (innerText), ale job ID z page 2 nejsou nikdy přidána do seznamu.
* **Fyzikální realita:** `_extract_job_ids()` vrací všechny job ID na stránce včetně persistentních doporučených/sidebar jobů. Ty se nemění napříč stránkami. Dedup per-page způsobí, že jakmile se první page ID shodují s persistentními, loop skončí. Řešení: sbírat všechna ID napříč stránkami, deduplikovat až na konci.
* **Korekce (Pravidlo):** Původní `new_ids` check nahrazen prostým `all_job_ids.extend(page_ids)`. Deduplikace na konci: `seen = set(); deduped = [jid for jid in all_job_ids if not (jid in seen or seen.add(jid))]; all_job_ids[:] = deduped`. Zachovává pořadí, odstraňuje duplicity, nebrání loopu v pokračování na další stránky.

---

## ZÁZNAM 017: Browser profile lock při druhém běhu

* **Symptom:** `uv run python -c "..."` selhal s `TargetClosedError: BrowserType.launch_persistent_context: Target page, context or browser has been closed`. Chrome log: "Otevírám v existující relaci prohlížeče."
* **Příčina:** MCP server používal persistentní Chrome profil v `~/.linkedin-mcp-custom/profile/`. Druhý Python proces (CLI pipeline) se pokusil otevřít stejný profil → Chrome detekuje locked profile → zkouší otevřít v existující session → selže (remote debugging pipe není sdílená mezi procesy).
* **Fyzikální realita:** Chrome persistent context (user data dir) je zámek na úrovni souborového systému. `launch_persistent_context()` vytvoří zámek (`SingletonLock` nebo `ChromeProfileLock`). Druhý proces nemůže stejný profil otevřít, dokud první neuvolní. Patchright to hlásí jako `TargetClosedError`, ne jako "profile locked" — matoucí.
* **Korekce (Pravidlo):** Před CLI runem zavřít MCP browser session: `close_session_tool` → uvolní profil → CLI run → restart MCP server. Nebo použít `connect_over_cdp` pokud server běží s `--remote-debugging-port`.

## ZÁZNAM 018: InnerText extraction funguje, DOM extraction ne (duální realita tracker page)

* **Symptom:** `_extract_inner_text()` na page 2 vrací 7 nových jobů (CEE Pricing Data Domain Lead, AI Developer atd.). `_extract_job_ids()` na stejné page vrací PRÁZDNÝ seznam (později stejná ID). Text a DOM jsou v rozporu.
* **Příčina:** LinkedIn tracker používá hybridní rendering: (a) `<main>` element s React-rendered textem — innerText obsahuje všechna data. (b) Job karty jako divy/sectiony bez `<a href>` — navigace přes JS click handlery. (c) Doporučené joby v sidebaru jako `<a href="/jobs/view/ID">` — persistentní napříč stránkami. Výsledek: innerText vidí vše, DOM selectory vidí jen doporučené.
* **Fyzikální realita:** Na LinkedIn tracker page existují DVĚ sady jobů:
  1. **Hlavní seznam** (React state, žádná URL v DOM) — viditelný jen v innerText
  2. **Doporučené/similar joby** (`<a href="/jobs/view/ID">`) — persistentní, dostupné přes DOM
  Job ID hlavního seznamu jsou serializována pouze v inline `<script>` blocích jako `jobPosting:4435589028`. Bez prohledávání script tagů jsou neviditelná.
* **Korekce (Pravidlo):** Nikdy nepoužívat DOM selectory jako jediný zdroj job ID na tracker page. Vždy kombinovat innerText (pro detekci existence) + script JSON scan (pro ID) + `<a href>` (pro doporučené). Pokud innerText ukazuje job, ale ID není nikde v DOM — fallback: scrape job detail přes title+company vyhledávání.

---

*pitevni_kniha_v1.md — vytvořeno 2026-07-05, aktualizováno 2026-07-07 — záznamy 001–018*
