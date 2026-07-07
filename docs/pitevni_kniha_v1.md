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

---

*pitevni_kniha_v1.md — vytvořeno 2026-07-05 — záznamy 001–006*
