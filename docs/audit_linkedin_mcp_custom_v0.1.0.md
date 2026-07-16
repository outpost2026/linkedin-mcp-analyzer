

**AUDITNÍ ZPRÁVA**

**linkedin-mcp-custom v0.1.0**

*Komplexní technický audit: architektura, MCP zralost, LinkedIn scraping strategie, EROI scoring, testování a publish-readiness*


**Zdrojové podklady: **audit\_prompt\_linkedin\_mcp\_custom.md (commit bd5b5dc), error\_analysis\_20260715\_194245.json

**Analyzovaný běh: **pipeline\_20260715\_194245 — 4/50 úloh oskórováno, 46/50 selhalo

**Datum vypracování: **16. 7. 2026

**Metoda: **Cross-LLM audit dle šablony MCP-Jobs audit\_prompt\_v1.1.docx



# Obsah

**1. Shrnutí pro vedení**

**2. Kořenová analýza selhání běhu (92 % chybovost)**

**3. Přezkum iterací P1–P4**

**4. Tabulka zjištění**

**5. Skóre kvality kódu podle modulu**

**6. Posouzení LinkedIn scraping strategie**

**7. Správnost EROI scoringu**

**8. Testování a kvalita**

**9. Připravenost k publikaci (Publish-Readiness)**

**10. Návrhy řešení**

**11. Návrhy rozvoje MCP serveru**

**12. Prioritizovaný plán pro iteraci v0.2.0**

**13. Závěr a doporučení**


# 1. Shrnutí pro vedení

## 1.1 Přehled

linkedin-mcp-custom (v0.1.0, pre-release, single-developer) je MCP server, který stahuje uložené pracovní nabídky z LinkedIn pomocí prohlížeče Patchright, skóruje je šestidimenzionálním EROI modelem a zapisuje výsledky do gitového repozitáře B2B-Knowledge-Base. Tento audit vychází ze zdrojového kódu při commitu bd5b5dc a z konkrétních chybových dat běhu pipeline\_20260715\_194245, ve kterém bylo z 50 nalezených úloh oskórováno pouze 4 (8 %), zatímco 46 (92 %) selhalo.

Cílem auditu je nejen zopakovat již známé nálezy z error\_analysis JSON, ale nezávisle prověřit hypotézy, dohledat kořenové příčiny v kódu a navrhnout konkrétní, proveditelná řešení včetně rozvoje MCP vrstvy serveru.

## 1.2 Tři nejdůležitější zjištění

- **F-01/F-02 (Kritická): **92% chybovost běhu má dvě vrstvy příčin — (a) LinkedIn pravděpodobně tiše blokuje/zavěšuje navigace na /jobs/view/ po ~2 úspěšných zobrazeních v rámci session, a (b) job\_timeout\_seconds=120, dokumentovaný jako timeout na jednu úlohu, se v praxi chová jako sdílený časový rozpočet celé dávkové fáze — 29 úloh vykazuje naprosto identickou dobu trvání 120,0 s, což ukazuje na jeden společný časovač, nikoli na 29 nezávislých. To zkresluje diagnostiku a znásobuje dopad původního problému.

- **F-04 (Závažná): **Nesrovnalost mezi skóre a verdiktem — úloha 4439059407 (System Architect, Škoda Group) má total\_score 35,9, tedy nad prahem hranicni (30,0), přesto je označena verdiktem NESLEDOVAT namísto očekávaného HRANICNI. To je ověřitelné přímo dopočítáním z config\_snapshot.thresholds a zpochybňuje důvěryhodnost všech vykázaných verdiktů, dokud nebude vysvětleno.

- **F-06 (Závažná): **Nulové pokrytí testy pro extractor.py, browser.py a auth.py — tedy přesně tu část systému, která je zdrojem 100 % aktuálních selhání. Bez mockovaného testovacího rámce pro Page/BrowserContext nelze žádnou opravu regresně ověřit jinak než opakovaným tříbením proti živému LinkedInu, což riziko rate-limitingu ještě zvyšuje.

## 1.3 Health Score

**5 / 10 ***(potvrzeno nezávisle, shoduje se se sebehodnocením v zadání)*

Architektonické základy jsou solidní (čistý dataclass config, jasně oddělené scoring dimenze, graceful degradation, funkční page pool s drainováním). Skóre drží uprostřed škály kombinace tří faktorů: (1) provozní nespolehlivost blokující reálné použití, (2) nově odhalené chyby v samotné scoringové logice, které mohly dosud procházet bez povšimnutí, a (3) chybějící testové pokrytí přesně tam, kde vzniká nejvíc rizika.

## 1.4 Doporučení Go / No-Go pro v0.2.0

**Podmíněné NE-GO. **Release v0.2.0 (natož veřejné/komunitní oznámení) nedoporučuji, dokud nebudou vyřešeny položky P0 z kapitoly 12 (oprava ukotvení per-job timeoutu, pipeline-level backoff, diagnostické logování HTTP odpovědí a ověření verdiktové nesrovnalosti). Tyto čtyři položky jsou malého až středního rozsahu (řádově hodiny až jeden až dva dny) a jejich nesplnění by znamenalo, že první kontakt jakéhokoli externího uživatele s nástrojem bude 92% chybovost.


# 2. Kořenová analýza selhání běhu (92 % chybovost)

Toto je klíčová část auditu — jde nad rámec pouhého zopakování error\_analysis\_20260715\_194245.json a propojuje pozorovaná data s konkrétním chováním kódu v core/browser.py, core/auth.py a scripts/run\_pipeline.py.

## 2.1 Pozorovaný vzorec

Ulohy 1-2:    USPECH (7,7-15,6 s na ulohu)

Ulohy 3-22:   TIMEOUT presne na 15,0 s (100% selhani po 2 uspesich)

Ulohy 23-50:  Nikdy nezahajily goto() - timeout na urovni faze pri 120,0 s

*Vzorec konzistentní napříč 3+ běhy v okně 19:00–19:42. V 18:00 proběhl týž pipeline s úspěšností 50/50.*

## 2.2 Hypotéza A — LinkedIn rate-limiting / tiché blokování (potvrzeno jako pravděpodobnější)

- Binární charakter selhání (přesně 2 úspěchy, pak 100 % selhání) je typický pro server-side gate, nikoli pro postupnou degradaci.

- Všech 17 timeoutů má identickou dobu trvání ~15,0 s — goto() se nikdy nedočká odpovědi (ani chybové), což odpovídá tichému zahození/odepření spojení, ne pomalému renderu.

- Kontrola session (goto na /feed/) v témže běhu prošla za 10,5 s bez problému — blokace je tedy specifická pro endpoint /jobs/view/, ne pro celou doménu LinkedIn.com.

- P12 (MAX\_POOL\_SIZE vs. MAX\_CONCURRENT mismatch) byl již opraven na komitu bd5b5dc — pool i concurrency jsou nyní shodně 3, a přesto se kaskáda opakuje. To oslabuje hypotézu B (vyčerpání prostředků prohlížeče), protože ta by po opravě poolu měla z velké části vymizet.

## 2.3 Hypotéza B — vyčerpání prostředků Chromia (spíše zamítnuta)

Vyčerpání page poolu / vláken by typicky vedlo k postupné degradaci (rostoucí latence, sporadické TargetClosedError, různorodé chybové zprávy), nikoli k ostrému binárnímu přechodu po přesně dvou úlohách s identickými 15,0s timeouty. Navíc P15 (\_drain\_pending\_navs) hlásí 0 výskytů TargetClosedError v tomto běhu — pokud by šlo o vyčerpání prostředků prohlížeče, očekávali bychom zde stopy. Doporučuji hypotézu B považovat za sekundární a nepotvrzenou, dokud diagnostika z kap. 2.5 neprokáže opak.

## 2.4 Nové zjištění: sdílený časovač namísto per-job budgetu (F-02)

Toto je zjištění, které v původním error\_analysis JSON chybí, přestože je z dodaných dat dokazatelné. Kategorie job\_timeout\_120s uvádí 29 úloh, každá s duration\_seconds přesně 120,0 — nikoli 119,7 / 118,2 / 121,4 apod., jak by se dalo očekávat u 29 nezávisle běžících asyncio.wait\_for(..., timeout=120) časovačů spuštěných v různých okamžicích (různá pozice ve frontě semaforu). Naprostá shoda hodnoty u všech 29 položek je silným signálem, že reálně existuje jediný sdílený časový bod (začátek per-job fáze, t=0), nikoli 29 individuálních časovačů vázaných na okamžik, kdy daná úloha skutečně získá page ze semaforu.

Prakticky to znamená: job\_timeout\_seconds je v run\_pipeline.py zdokumentován a v tabulce 2.3 zdrojového zadání hodnocen jako „SOLID — prevents single job hanging pipeline“, ale chová se jinak, než se předpokládá. Úloha zařazená pozdě ve frontě nedostává vlastních 120 sekund od chvíle, kdy se jí reálně dostane page — dědí zmenšující se rozpočet z jednoho společného odpočtu, který běží od začátku fáze bez ohledu na to, jestli úloha vůbec začala pracovat. Důsledek: jakmile LinkedIn kolem 3. úlohy začne blokovat, všechny další fronty čekající úlohy jsou odsouzeny k společnému zániku v čase t=120 s, bez ohledu na to, jak dlouho skutečně čekaly nebo pracovaly.

**Proč na tom záleží: **46 nahlášených selhání jsou fakticky důsledkem jediné kořenové příčiny (LinkedIn blokace po 2. úloze), ale kód je kvůli tomuto designu vykazuje jako dvě odlišné kategorie chyb (navigation\_timeout\_15s a job\_timeout\_120s) s odlišnými "observed\_pattern" popisy. To ztěžuje budoucí diagnostiku a odvádí pozornost od skutečné jediné příčiny.

## 2.5 Diagnostický plán k potvrzení

- Zalogovat resp.status() a resp.headers() z návratové hodnoty page.goto() — pokud LinkedIn vrací HTTP 429/503, hypotéza A je potvrzena přímo; pokud spojení nikdy nedostane odpověď (network idle / connection reset), jde o silnější formu blokace (např. na úrovni TCP/TLS).

- Zalogovat tři časové značky na úlohu: čas vytvoření tasku, čas získání page ze semaforu, čas zahájení goto(). To okamžitě potvrdí nebo vyvrátí zjištění z kap. 2.4 — pokud je časový rozestup mezi vytvořením tasku a získáním page u pozdějších úloh blízko 120 s, sdílený časovač je prokázán.

- Spustit pipeline s max\_concurrent=1 (sekvenčně) — pokud selhání zmizí nebo se výrazně sníží, podporuje to spíše detekci souběžného přístupu než plošné vyčerpání zdrojů.

- Zvýšit per\_job\_timeout\_ms na 30000 jako kontrolní běh — pokud LinkedIn skutečně jen zpomaluje (a neblokuje trvale), delší okno by mělo obnovit část úspěšnosti.


# 3. Přezkum iterací P1–P4

Nezávislé hodnocení kvality nedávných oprav (commity f3a5048 → bd5b5dc), doplněné o kontext z kapitoly 2.

| **Změna** | **Hodnocení** | **Komentář** |
| - | - | - |
| **P1 — wait\_for\_selector('main') místo wait\_for\_timeout(2000)** | **SOLID** | **Potvrzeno v logách, ~40% zrychlení na úlohu, když LinkedIn odpovídá rychle. Bez vedlejších efektů.** |
| **P1 — blokování zdrojů (image/font/media)** | **SOLID** | **Aktivní a funkční, ale nemá žádný vliv na rate-limiting (řeší šířku pásma, ne detekci chování).** |
| **P2 — \_retry\_goto s exponenciálním backoffem** | **ČÁSTEČNÉ** | **Logika backoffu je korektní, ale výchozí nastavení (timeout jako non-retryable) fakticky backoff pro dominantní scénář selhání vůbec nespouští — je aktivní jen pro chyby spojení, ne pro timeouty, které tvoří 100 % pozorovaných chyb.** |
| **P2 — timeout jako non-retryable (fail-fast 15 s)** | **SOLID** | **Správné rozhodnutí — zabraňuje zablokování poolu opakovanými pokusy o nedostupný endpoint.** |
| **P2 — per-job timeout (asyncio.wait\_for 120 s)** | **REGRESE / NUTNÁ OPRAVA** | **Viz kap. 2.4 — funguje jako sdílený časovač fáze, ne jako izolovaný per-job budget. Zamýšlený efekt ("prevents single job hanging pipeline") je jen částečně naplněn a má nežádoucí vedlejší efekt kaskádového umlčení fronty.** |
| **P3 — sledování page poolu + drain před uzavřením** | **SOLID** | **Eliminovalo TargetClosedError varování — potvrzeno 0 výskytů v analyzovaném běhu.** |
| **P4 — YAML config (AppConfig dataclass)** | **SOLID** | **Čisté načítání/ukládání/override, dobře typované, žádné zjištěné problémy.** |
| **Auth cache DEBUG log v paralelní fázi (P8 fix)** | **SOLID** | **Snížení šumu v logu, cache zůstává platná i při per-job fázi 120 s.** |


Shrnutí: 6 ze 8 sledovaných změn je hodnoceno SOLID, 1 ČÁSTEČNĚ (P2 backoff) a 1 vyžaduje opravu (P2 per-job timeout — viz F-02, kap. 2.4 a 10.1). Tým opakovaně dobře řeší symptomy (rychlost, drain, config), ale poslední dvě iterace (P2) zavedly jemný, těžko postřehnutelný bug právě v mechanismu, který měl systém chránit před kaskádou.


# 4. Tabulka zjištění

Legenda závažnosti: Kritická = blokuje použitelnost/důvěryhodnost; Závažná = významné riziko nebo dluh; Menší = vylepšení; Info = k ověření/dokumentaci. Sloupec EROI vyjadřuje poměr přínosu k nákladu opravy (Effort-to-Return On Investment), nikoli EROI scoring z domény produktu.

| **ID** | **Oblast** | **Závažnost** | **Zjištění** | **Doporučení** | **EROI** |
| - | - | - | - | - | - |
| **F-01** | **LinkedIn scraping** | **Kritická** | **/jobs/view/ endpoint po ~2 úspěšných přístupech ze session 100% blokuje/zavěšuje navigace (goto timeout 15 s, 17/50 úloh).** | **Zavést pipeline-level backoff (kap. 10.2) + logovat HTTP status/typ chyby z goto() pro potvrzení.** | **Vysoký** |
| **F-02** | **Architektura / pipeline** | **Kritická** | **job\_timeout\_seconds=120 se chová jako sdílený časovač celé per-job fáze místo nezávislého budgetu na úlohu — 29 úloh má identickou dobu 120,0 s.** | **Ukotvit wait\_for() k okamžiku získání semaforu/page, ne k začátku fáze (kap. 10.1).** | **Vysoký** |
| **F-03** | **Architektura / pipeline** | **Závažná** | **Chybí pipeline-level rate-limit backoff — po sérii selhání pipeline dál nekompromisně zkouší další úlohy stejným tempem.** | **Rolling-window sledování poměru selhání s pauzou 30–120 s (kap. 10.2).** | **Vysoký** |
| **F-04** | **EROI scoring** | **Závažná** | **Úloha 4439059407 (score 35,9) je označena NESLEDOVAT, ačkoli 35,9 ≥ hranicni (30,0) → dle scorer.py by měla být HRANICNI.** | **Ověřit shodu verdiktu mezi scorer.py.\_threshold\_verdict a cestou, kudy verdikt prochází do report\_generator.py / pipeline reportu; může jít i o artefakt sestavení tohoto JSON.** | **Vysoký** |
| **F-05** | **EROI scoring** | **Závažná** | **growth\_score() bere v úvahu pouze název firmy (2 statické seznamy, 23 firem celkem) a zcela ignoruje text inzerátu — neznámý startup vždy dostane plochých 20 bodů bez ohledu na textové signály růstu.** | **Rozšířit signaturu na growth\_score(company, text) a doplnit keyword scan (Series A/B/C, fast-growing, scale-up, nábor…) jako sekundární signál.** | **Střední** |
| **F-06** | **Testování** | **Závažná** | **0 testů pro extractor.py, browser.py, auth.py — přesně ty moduly, které aktuálně produkují 100 % chyb běhu.** | **AsyncMock(spec=Page) pro jednotkové testy + lokální fixture server pro E2E bez zásahu do produkčního LinkedInu (kap. 8, 10.5).** | **Vysoký** |
| **F-07** | **Kvalita kódu** | **Závažná** | **KBWriter (396 řádků) míchá 3 odpovědnosti: metadata JSON, markdown report, git operace — porušení SRP, ztěžuje testování.** | **Rozdělit na MetadataStore, MarkdownReportWriter, GitCommitter za fasádou KBWriter.** | **Střední** |
| **F-08** | **MCP architektura** | **Závažná** | **KBWriter.commit\_changes() pravděpodobně volá git synchronně uvnitř async MCP tool handleru — riziko zablokování event loop pro souběžné požadavky.** | **Přesunout na asyncio.to\_thread() nebo asyncio.create\_subprocess\_exec().** | **Střední** |
| **F-09** | **MCP zralost** | **Menší** | **L2 Resources nejsou implementovány — žádné přímé URI zpřístupnění úloh/reportů pro MCP klienty.** | **Navrhnout a implementovat linkedin-mcp://jobs/\{id\} a linkedin-mcp://analysis/reports/\{date\} (kap. 11.1).** | **Střední** |
| **F-10** | **MCP zralost** | **Menší** | **@mcp.prompt() není implementován — chybí asistované sestavení EROI dotazu nebo interpretace výsledku.** | **eroi\_query\_builder a interpret\_eroi\_result prompty (kap. 11.2).** | **Nízký** |
| **F-11** | **MCP UX** | **Menší** | **Průběh dávkového zpracování se hlásí přes ctx.info() log zprávy místo strukturovaného progress reportingu.** | **Přejít na ctx.report\_progress(current, total) v cyklu analyze\_saved\_jobs (kap. 11.3).** | **Nízký** |
| **F-12** | **EROI scoring** | **Menší** | **FAKE\_ENGINEER\_KEYWORDS obsahuje jen 8 termínů — tenké pokrytí, riziko falešně pozitivních i negativních klasifikací rolí.** | **Iterativně rozšiřovat na základě logovaných neshod (role\_score \< 40 vs. ruční posouzení).** | **Nízký** |
| **F-13** | **LinkedIn scraping** | **Menší** | **"Specific job list selector not found" se objevuje při každé stránkování — funguje fallback, ale bez měření četnosti nelze zachytit blížící se úplné selhání.** | **Přidat metriku četnosti fallbacku + hlasité selhání při překročení prahu (např. 80 %).** | **Nízký** |
| **F-14** | **Kvalita kódu** | **Menší** | **cli.py volá asyncio.run() v \_login/\_status; dnes nedosažitelné z běžícího event loopu, ale latentní riziko při budoucím znovupoužití uvnitř MCP tool handleru.** | **Oddělit čistou async logiku od asyncio.run() wrapperu, aby šla přímo awaitovat.** | **Nízký** |
| **F-15** | **Kvalita kódu** | **Info** | **analysis/config.py (262 řádků) drží klíčová slova jako Python literály — nižší editovatelnost pro netechnického uživatele, ale vyšší typová bezpečnost než YAML.** | **Ponechat v Pythonu, rozdělit po dimenzích do menších souborů; migraci na YAML řešit až při reálné potřebě needitovat kód.** | **Nízký** |
| **F-16** | **Publish-readiness** | **Závažná** | **Chybí LICENSE soubor.** | **Doplnit MIT nebo Apache-2.0 (kap. 9, 12).** | **Vysoký** |
| **F-17** | **Publish-readiness** | **Závažná** | **Chybí pyproject.toml / balíček není publikovatelný na PyPI.** | **Doplnit \[project\], \[project.scripts\] entry point, \[build-system\] (kap. 9).** | **Vysoký** |
| **F-18** | **Publish-readiness** | **Menší** | **Chybí Dockerfile pro stdio/SSE nasazení.** | **Multi-stage build s odděleným volume pro profil prohlížeče (kap. 9).** | **Střední** |
| **F-19** | **Traceability / EROI** | **Info** | **Zobrazené procentní hodnoty dimenzí ve výstupu (např. formal=20,0 % u úlohy 4418950272) neodpovídají žádné z diskrétních hodnot, které formal\_score() může vrátit (10/30/50).** | **Ověřit transformaci mezi EROIResult.to\_dict() a report\_generator.py — buď existuje nedokumentovaná úprava zobrazení, nebo se použitá verze formal.py liší od auditované.** | **Střední** |


# 5. Skóre kvality kódu podle modulu

Škála 1 (nízká) – 5 (vysoká). MCP = relevance/soulad s MCP best practices (u modulů mimo MCP transportní vrstvu vyjadřuje nepřímý dopad na MCP server jako celek).

| **Modul** | **Čitelnost** | **Testovatelnost** | **Robustnost** | **MCP** | **Průměr** |
| - | - | - | - | - | - |
| **server.py** | **5** | **4** | **4** | **4** | **4,25** |
| **tools/job.py** | **3** | **3** | **4** | **4** | **3,50** |
| **cli.py** | **4** | **2** | **3** | **2** | **2,75** |
| **config.py** | **5** | **4** | **4** | **3** | **4,00** |
| **core/browser.py** | **4** | **2** | **4** | **3** | **3,25** |
| **core/auth.py** | **4** | **2** | **3** | **3** | **3,00** |
| **core/exceptions.py** | **5** | **5** | **5** | **3** | **4,50** |
| **scraping/extractor.py** | **2** | **1** | **3** | **3** | **2,25** |
| **scraping/utils.py** | **5** | **5** | **4** | **2** | **4,00** |
| **analysis/scorer.py** | **5** | **4** | **3** | **3** | **3,75** |
| **analysis/domain.py** | **5** | **4** | **4** | **2** | **3,75** |
| **analysis/tech.py** | **5** | **4** | **4** | **2** | **3,75** |
| **analysis/role.py** | **5** | **4** | **4** | **2** | **3,75** |
| **analysis/growth.py** | **5** | **4** | **2** | **2** | **3,25** |
| **analysis/kb\_writer.py** | **2** | **3** | **4** | **2** | **2,75** |
| **analysis/report\_generator.py** | **3** | **4** | **3** | **2** | **3,00** |
| **scripts/run\_pipeline.py** | **3** | **1** | **3** | **1** | **2,00** |


Nejnižší skóre má scripts/run\_pipeline.py (2,00) — 572 řádků bez jediného testu, a právě zde s velkou pravděpodobností žije bug z F-02. Těsně za ním extractor.py (2,25) — jádrová scraping logika bez testů a se 110+řádkovou metodou scrape\_job(). Tyto dva moduly tvoří přirozenou prioritu pro kapitolu 10 (Testování) a 12 (Roadmap).


# 6. Posouzení LinkedIn scraping strategie

## 6.1 Účinnost současných obran

| **Obrana** | **Stav** | **Hodnocení účinnosti** |
| - | - | - |
| **Headless prohlížeč** | **Zapnuto** | **Nutné pro JS rendering; zvyšuje detekovatelnost oproti headful.** |
| **Blokování zdrojů (image/font/media)** | **Zapnuto** | **Šetří šířku pásma, na rate-limiting nemá vliv.** |
| **Persistentní profil** | **Zapnuto** | **Cookies přežívají restart; nutné pro session-based auth.** |
| **Per-job timeout 15 s** | **Zapnuto** | **Fail-fast, brání zablokování poolu — funguje dle záměru.** |
| **Exponenciální backoff na goto** | **Zapnuto (jen chyby spojení)** | **Timeout je non-retryable — pro dominantní scénář selhání se nespouští.** |
| **Pipeline-level backoff** | **Vypnuto** | **Chybí — hlavní doporučená obrana proti rate-limitingu (F-03).** |
| **Sekvenční fallback** | **Vypnuto** | **Chybí — zabránilo by kaskádě z F-02.** |
| **Náhodné prodlevy mezi požadavky** | **Vypnuto** | **Absence pravidelného, strojového rytmu (stagger\_delay=1,5 s je fixní) usnadňuje detekci vzorce.** |

## 6.2 Analýza rizika rate-limitingu

Kombinace fixního stagger\_delay=1,5 s a max\_concurrent=3 vytváří velmi pravidelný, strojový vzorec přístupu ke stránkám /jobs/view/ — tři souběžné požadavky opakovaně v přesném rytmu jsou z pohledu bot-detekce silnější signál než sekvenční přístup s náhodnou prodlevou. Otázka ze zadání (6.3.3) "zvyšuje paralelní přístup riziko detekce?" má dle dostupných indicií odpověď spíše ANO: pozorovaný vzorec (2 úspěchy → 100% selhání) je konzistentnější s detekcí založenou na chování relace než s prostou kvótou počtu požadavků, protože fixní paralelní zátěž ze stejné autentizované session je snáz rozpoznatelná jako automatizace než rozprostřený sekvenční provoz.

## 6.3 Doporučené upgrady obrany

- Výchozí max\_concurrent=1 se sekvenčním zpracováním a náhodnou prodlevou 2–5 s mezi úlohami; paralelní režim (2–3) ponechat jako explicitní "rychlý režim" s varováním o zvýšeném riziku.

- Pipeline-level backoff dle kap. 10.2 — sledovat posledních N=5 výsledků, při \>50 % selhání pauza 30 s → 60 s → 120 s (exponenciálně, s reset oknem po úspěchu).

- Logovat HTTP status a typ chyby z goto() — bez toho nelze hypotézu A formálně potvrdit ani odlišit HTTP 429 od tichého zahození spojení.

- Metrika četnosti fallbacku pro "selector not found" (F-13) — časné varování před rozsáhlejším driftem DOM struktury jobs-tracker.


# 7. Správnost EROI scoringu

## 7.1 Verdiktová nesrovnalost (F-04) — detailní rozbor

| **Job ID** | **Titul** | **Firma** | **Skóre** | **Verdikt v reportu** | **Konzistence s prahy** |
| - | - | - | - | - | - |
| **4440959667** | **AI & Automation Specialist** | **Reas.cz** | **22,9** | **NESLEDOVAT** | **OK (\< 30,0)** |
| **4439059407** | **System Architect** | **Škoda Group** | **35,9** | **NESLEDOVAT** | **NESEDÍ — dle prahů odpovídá HRANICNI (30,0–44,9)** |
| **4437314242** | **Product Owner – AI, Automation & Tooling** | **Aeven** | **23,4** | **NESLEDOVAT** | **OK (\< 30,0)** |
| **4418950272** | **Aplikační inženýr (Machine Vision)** | **Averna** | **24,9** | **NESLEDOVAT** | **OK (\< 30,0)** |


Prahy z config\_snapshot: sledovat=70,0, medium=45,0, hranicni=30,0. Dle scorer.py.\_threshold\_verdict má skóre 35,9 spadat do pásma HRANICNI (30,0 ≤ x \< 45,0), ne NESLEDOVAT. Jde o jediný rozpor ze 4 úloh — tři zbylé jsou interně konzistentní, což ukazuje spíš na okrajový/edge-case bug (např. porovnání s jiným prahem, zaokrouhlovací chyba, nebo odlišná sada prahů v době skórování oproti config\_snapshot) než na systémovou chybu ve všech verdiktech. Nelze vyloučit ani to, že šlo o chybu při ručním sestavování tohoto konkrétního error\_analysis JSON pro cross-LLM review, oddělenou od zdrojového pipeline\_20260715\_194245.json. V obou případech doporučuji ověření přímo v pipeline\_20260715\_194245.json (surový výstup), než se cokoliv opravuje v kódu.

## 7.2 Odpovědi na dílčí otázky zadání (6.4)

### Domain (35 %) a Tech (25 %) — pokrytí seznamů klíčových slov

Bez plného obsahu CORE\_INDUSTRIAL\_KEYWORDS / SKILL\_MATRIX (v podkladech jsou jen počty: 45/16/24 pro domain, 43 skillů pro tech) nelze pokrytí ověřit s jistotou. Vzhledem k vlastnímu pozicování Ondřeje na CNC/průmyslovou automatizaci doporučuji explicitně ověřit přítomnost termínů PLC, SCADA, MES, IIoT a edge computing v SKILL\_MATRIX — jejich absence by byla kritickou mezerou právě pro cílový segment trhu.

### Role (20 %) — FAKE\_ENGINEER\_KEYWORDS

8 termínů je tenké pokrytí. role\_score() navíc pracuje binárně (title\_has\_engineering × text\_has\_fake), takže i jeden nešťastně zvolený marketingový obrat v popisu inzerátu (např. „customer-facing engineering role“) může strhnout skóre z 85 na 40. Doporučeno postupné rozšiřování na základě zpětné vazby, ne jednorázová revize.

### Growth (10 %) — zaujatost vůči známým zaměstnavatelům

Potvrzeno: growth\_score(company) bere pouze název firmy proti dvěma statickým seznamům (11 strategických + 12 růstových = 23 firem). Neznámá firma dostává vždy plochých 20 bodů bez ohledu na to, co o svém růstu píše přímo v textu inzerátu — funkce text vůbec nedostává jako parametr. Toto je jednoznačná a snadno opravitelná mezera (viz F-05 a kap. 10.3).

### Proč všechny 4 úspěšné úlohy skončily NESLEDOVAT

Nejpravděpodobnější vysvětlení není přehnaná přísnost scoringu, ale malá velikost vzorku (4 z 50 plánovaných) v kombinaci s tím, že šlo o obecnější/IT-manažerské role (System Architect, Product Owner, AI Specialist) spíše než o úzce CNC/průmyslové pozice, pro které je model laděn. Se vzorkem 4 úloh nelze kalibraci modelu ani potvrdit, ani vyvrátit — validace scoringu je podmíněna vyřešením F-01/F-02, aby bylo možné znovu získat plný vzorek 50/50.

## 7.3 Traceability nález (F-19)

Hodnoty dimenzí zobrazené ve výstupu běhu (např. domain=15,0 %, tech=8,5 % pro úlohu Reas.cz) se nedaří jednoznačně zrekonstruovat ani jako syrové skóre dimenze (formal\_score() může vracet jen 10/30/50, ale u úlohy Averna je zobrazeno 20,0 %), ani jako jednoduchý součin skóre × váhy. To naznačuje, že mezi EROIResult.to\_dict() a finálním zobrazením v reportu existuje další, needokumentovaná transformace (pravděpodobně v report\_generator.py, který byl v podkladech dodán jen jako shrnutí, ne plný zdrojový kód). Doporučuji tento úsek zdrojového kódu prověřit samostatně — bez něj audit nemůže s jistotou potvrdit ani vyvrátit správnost zobrazovaných procent, jen upozornit na rozpor.


# 8. Testování a kvalita

## 8.1 Aktuální stav

29 testů, 0 selhání, běh ~18 s. Pokrytí je silné pro čistě funkční, bezstavové části (EROI scoring, KBWriter, report generator), ale nulové pro vše, co se dotýká Patchright/Page — tedy přesně tu vrstvu, kde vznikají všechna aktuální selhání.

## 8.2 Strategie testování extractor.py bez reálného prohlížeče

- Použít unittest.mock.AsyncMock(spec=Page) — mock je typově vázaný na skutečné rozhraní Playwright Page, takže odhalí drift, pokud extractor.py začne volat metodu, která na Page reálně neexistuje.

- Testovat čistě funkční jednotky (\_extract\_job\_metadata, \_extract\_job\_ids, strip\_noise) přímo na uložených, anonymizovaných innerText fixture datech ze skutečných LinkedIn stránek — bez závislosti na Playwright vůbec.

- Pro navigate\_to\_page/extract\_page (skutečná interakce s Page rozhraním) postačí AsyncMock se scénáři: úspěch, timeout, checkpoint stránka, prázdný obsah.

## 8.3 Jsou nutné integrační testy proti živému LinkedInu?

Ne jako výchozí strategie. Opakované automatizované testy proti produkčnímu LinkedInu by samy zvyšovaly riziko rate-limitingu — tedy přesně jevu, který je předmětem tohoto auditu. Doporučuji lokální fixture server (např. aiohttp test app nebo pytest-httpserver) obsluhující staticky uložené, sanitizované HTML snímky reálných stránek, proti kterému Patchright skutečně naviguje na http://localhost:PORT/jobs/view/123. To dává reálné pokrytí interakční vrstvy (selektory, wait\_for chování, scrollování) bez dotyku produkčního LinkedInu.

## 8.4 Je mockování v test\_batch\_pipeline.py dostatečné?

unittest.mock.patch na celý LinkedInExtractor ověří orchestraci dávky a deadline logiku v tools/job.py, ale neodhalí reálné async/await chyby — mock vrátí přesně to, co je nakonfigurováno, bez ohledu na to, zda skutečná implementace correctly awaituje. Doporučuji doplnit AsyncMock(spec=LinkedInExtractor) pro odchycení signaturového driftu a kombinovat s fixture-server testy z 8.3 pro chování za běhu.

## 8.5 Odhad dopadu 10 nových testů s mockovaným prohlížečem

Při použití AsyncMock (bez reálného spuštění prohlížeče) je náklad na test typicky pod 100 ms — celkový dopad na dobu běhu sady řádově +1 až +2 s, sada zůstane pohodlně pod 20 s. Pokud by se místo mocku použil reálný (headless) Patchright i jen proti lokálním fixture souborům, doporučuji session-scoped fixture prohlížeče (spuštění jednou, sdílené napříč testy) — jinak hrozí kumulativní režie 10–20 s jen na opakované spouštění prohlížeče.


# 9. Připravenost k publikaci (Publish-Readiness)

## 9.1 Podmíněné doporučení

**NE-GO **pro veřejné oznámení / PyPI release, dokud nebudou vyřešeny blokující položky níže. Repozitář má 0 hvězd, 0 forků, 0 přispěvatelů — první dojem externího uživatele by dnes byl 92% chybovost, což je nevratně poškozující pro adopci nástroje s tak úzkým cílovým trhem (CZ/NL průmyslová automatizace).

## 9.2 Mezery — blokující vs. nice-to-have

| **Mezera** | **Klasifikace** | **Odhad** | **Poznámka** |
| - | - | - | - |
| **LICENSE soubor chybí** | **Blokující** | **15 min** | **MIT nebo Apache-2.0 — pro tenhle rozsah nástroje postačí MIT, Apache-2.0 navíc dává patentovou ochranu.** |
| **pyproject.toml / PyPI balíčkování** | **Blokující** | **2–4 h** | **\[project.scripts\] entry point, závislosti (fastmcp, patchright, pyyaml), classifiers.** |
| **CONTRIBUTING.md + issue templates** | **Nice-to-have** | **1–2 h** | **Minimální komunitní balíček — bug\_report.md, feature\_request.md.** |
| **SECURITY.md / poznámka o ToS LinkedIn** | **Blokující (právní jasnost)** | **1 h** | **Explicitní upozornění, že automatizace LinkedInu bez oficiálního API může porušovat Terms of Service; uživatel nese odpovědnost.** |
| **.gitignore pro ~/.linkedin-mcp-custom/profile/** | **Blokující (bezpečnost)** | **15 min** | **Profil obsahuje reálné session cookies — nutno ověřit, že adresář nikdy nekončí v gitu.** |
| **Dockerfile** | **Nice-to-have** | **3–5 h** | **Multi-stage build; profil prohlížeče jako mountovaný volume, ne pečený do image.** |
| **CI spouští testy (dnes jen outputs)** | **Nice-to-have** | **1 h** | **GitHub Actions workflow existuje, ale dle zadání zatím jen produkuje výstupy, ne gate na testy.** |

## 9.3 Bezpečnost

Persistentní profil prohlížeče (core/browser.py: PROFILE\_DIR = ~/.linkedin-mcp-custom/profile) obsahuje reálné LinkedIn session cookies. Toto je citlivý materiál srovnatelný s přístupovým tokenem — doporučuji: (1) ověřit/doplnit .gitignore pravidlo pro tento adresář, (2) v README explicitně uvést, že adresář se nikdy nesdílí ani nekomituje, (3) zvážit volitelné šifrování profilu at-rest jako obranu do hloubky, zejména pokud bude nástroj nabízen širší komunitě.


# 10. Návrhy řešení

Konkrétní, proveditelné opravy pro kritická a závažná zjištění z kapitoly 4, seřazené podle závislostí (nejprve opravy, které umožní správně diagnostikovat zbytek).

## 10.1 Oprava sdíleného per-job timeoutu (F-02)

Kořen problému: wait\_for(job\_timeout) je pravděpodobně spuštěn v okamžiku vytvoření tasku (t=0 celé fáze), ne v okamžiku, kdy úloha skutečně získá page ze semaforu. Řešení: časovač ukotvit až za acquire semaforu, nebo úlohám čekajícím ve frontě přiznat vlastní, neredukovaný rozpočet.

\# scripts/run\_pipeline.py — konceptuální oprava

async def process\_one(job\_id: str):

    async with semaphore:                      \# čekání ve frontě NENÍ součástí timeoutu

        return await asyncio.wait\_for(

            extractor.scrape\_job(job\_id),

            timeout=job\_timeout\_seconds,        \# timer startuje AŽ ZDE

        )

*Klíčová změna: wait\_for() obaluje pouze samotnou práci uvnitř "async with semaphore", ne celý task od jeho vytvoření.*

Vedlejší přínos: po této opravě přestanou vznikat falešné job\_timeout\_120s záznamy pro úlohy, které se do práce vůbec nedostaly — error kategorie se zúží na skutečnou příčinu (F-01), což zjednoduší budoucí diagnostiku.

## 10.2 Pipeline-level backoff (F-01, F-03)

\# rolling-window backoff — konceptuální náčrt

recent\_outcomes: deque\[bool\] = deque(maxlen=5)  \# True = úspěch

backoff\_seconds = 30


for job\_id in job\_ids:

    if recent\_outcomes and sum(recent\_outcomes) / len(recent\_outcomes) \< 0.5:

        await asyncio.sleep(backoff\_seconds)

        backoff\_seconds = min(backoff\_seconds \* 2, 120)

    else:

        backoff\_seconds = 30                     \# reset po zotavení

    ok = await process\_one(job\_id)

    recent\_outcomes.append(ok)

Umístění: v run\_pipeline.py, na úrovni smyčky, která vytváří/spouští jednotlivé per-job tasky — ne uvnitř extractor.py, protože backoff je rozhodnutí na úrovni orchestrace dávky, ne jednotlivé navigace.

## 10.3 Diagnostické logování + rozšíření growth\_score (F-05)

- V \_retry\_goto zalogovat resp.status if resp else "no\_response" po každém pokusu — triviální změna s vysokou diagnostickou hodnotou (viz kap. 2.5).

- growth\_score(company, text) — přidat druhý parametr a keyword scan pro fráze typu „Series A/B/C“, „fast-growing“, „scale-up“, „rozšiřujeme tým“ jako sekundární signál, pokud firma není na žádném ze statických seznamů.

## 10.4 Sekvenční fallback + bezpečnější výchozí concurrency

Nastavit výchozí max\_concurrent=1 s náhodnou prodlevou 2–5 s (viz kap. 6.3) a doplnit automatický přechod na sekvenční režim, pokud v posledních N úlohách selhalo \>50 % — přesně dle P0 doporučení z error\_analysis JSON, zde jen doplněné o konkrétní výchozí hodnotu a zdůvodnění z kap. 6.2.

## 10.5 Refaktor KBWriter (F-07) a async-safe git (F-08)

class KBWriter:                    \# zůstává jako fasáda pro zpětnou kompatibilitu MCP tools

    def \_\_init\_\_(self):

        self.metadata = MetadataStore(...)

        self.report = MarkdownReportWriter(...)

        self.git = GitCommitter(...)


    def write\_all(self, eroi, raw\_text, linkedin\_job\_id):

        self.metadata.upsert(eroi, linkedin\_job\_id)

        self.report.append\_section(eroi, raw\_text)

        return self.git.commit\_async(...)        \# asyncio.to\_thread uvnitř GitCommitter


# 11. Návrhy rozvoje MCP serveru

Konkrétní návrh posunu po MCP zralostním žebříčku z kapitoly 4.2 zadání (L1 hotovo → L2/L3/L4 v tomto plánu).

## 11.1 L2 — Resources

| **URI schéma** | **Co zpřístupňuje** | **Přínos** |
| - | - | - |
| **linkedin-mcp://jobs/\{job\_id\}** | **Read-only snímek naposledy staženého inzerátu: title, company, location, raw\_text, scraped\_at.** | **Klient (např. Claude Desktop) může vložit konkrétní inzerát přímo do kontextu bez volání toolu a bez nové navigace.** |
| **linkedin-mcp://jobs/saved** | **Aktuální seznam uložených úloh (job\_ids + základní metadata z /jobs-tracker/).** | **Rychlý přehled bez nutnosti volat get\_saved\_jobs pokaždé znovu.** |
| **linkedin-mcp://analysis/reports/\{date\}** | **Konkrétní denní syntetický report (MD/JSON) z B2B-Knowledge-Base.** | **Přímý přístup k historickým reportům bez nutnosti volat generate\_report a parsovat soubory ručně.** |
| **linkedin-mcp://config** | **Aktuální AppConfig jako read-only introspekční zdroj.** | **Diagnostika a ladění bez nutnosti otevírat YAML soubor mimo MCP session.** |

## 11.2 L3 — Prompts

- **eroi\_query\_builder — **vezme neformální popis kritérií (např. „chci remote CNC-adjacent role v ČR u rostoucích firem“) a pomůže sestavit konkrétní volání analyze\_saved\_jobs s vhodným limit/job\_ids/threshold filtrem. Obdoba search\_expert promptu z MCP-Jobs.

- **interpret\_eroi\_result — **vysvětlí konkrétní EROIResult v přirozeném jazyce pro uživatele, který nezná vnitřní scoring logiku — proč skóre vyšlo tak, jak vyšlo, a co by jej nejvíc zvýšilo.

## 11.3 L4 — Streaming

Nahradit await ctx.info(f"\#\{jid\}: ...") strukturovaným await ctx.report\_progress(current=len(processed\_ids), total=len(job\_ids\_to\_process)) v cyklu analyze\_saved\_jobs — ctx.info() zůstává pro čitelné log řádky, report\_progress dává klientovi skutečný, renderovatelný progress bar pro dávky delší než 30 s. Jde o malou změnu (přidání jednoho volání do existující smyčky) s reálným UX přínosem.

## 11.4 L5/L6 — výhled

Multi-transport (SSE/HTTP vedle stdio) a orchestrace MCP-to-MCP (LinkedIn Analyzer ↔ Knowledge Base) zůstávají korektně označeny jako FUTURE/VISION — nedoporučuji se jimi zabývat před vyřešením kapitoly 12, P0–P1. Předčasná investice do L5/L6 na nespolehlivém L1 základu by jen znásobila plochu pro chyby.


# 12. Prioritizovaný plán pro iteraci v0.2.0

## P0 — blokující, řešit první

| **Priorita** | **Položka** | **Náročnost** | **Snížení rizika** | **Hodnota** |
| - | - | - | - | - |
| **P0-1** | **Oprava ukotvení per-job timeoutu (F-02, kap. 10.1)** | **S (hodiny)** | **Vysoké** | **Vysoká — přímo opravuje většinu nahlášených selhání** |
| **P0-2** | **Pipeline-level backoff (F-01/F-03, kap. 10.2)** | **S–M (den)** | **Vysoké** | **Vysoká** |
| **P0-3** | **Diagnostické logování HTTP status/chyby z goto()** | **Triviální** | **Střední** | **Vysoká — odemyká správnou diagnostiku dalších kroků** |
| **P0-4** | **Ověřit a opravit verdiktovou nesrovnalost (F-04, kap. 7.1)** | **S (hodiny)** | **N/A** | **Vysoká — důvěryhodnost celého scoringu** |

## P1 — vysoká priorita

| **Priorita** | **Položka** | **Náročnost** | **Snížení rizika** | **Hodnota** |
| - | - | - | - | - |
| **P1-1** | **Výchozí max\_concurrent=1 + náhodné prodlevy (kap. 6.3, 10.4)** | **S** | **Střední–vysoké** | **Střední–vysoká** |
| **P1-2** | **Sekvenční fallback při \>50 % selhání** | **M** | **Vysoké** | **Střední** |
| **P1-3** | **Testové pokrytí extractor.py (AsyncMock + fixture server, kap. 8)** | **M–L** | **Vysoké** | **Vysoká** |
| **P1-4** | **Refaktor KBWriter na 3 kolaborátory (F-07, kap. 10.5)** | **M** | **Střední** | **Střední** |
| **P1-5** | **Async-safe git operace (F-08, kap. 10.5)** | **S** | **Střední** | **Střední** |

## P2 — střední priorita

| **Priorita** | **Položka** | **Náročnost** | **Snížení rizika** | **Hodnota** |
| - | - | - | - | - |
| **P2-1** | **MCP L2 Resources (kap. 11.1)** | **M** | **Nízké** | **Střední** |
| **P2-2** | **MCP L4 structured progress (kap. 11.3)** | **S** | **Nízké** | **Střední** |
| **P2-3** | **growth\_score() textový signál (F-05, kap. 10.3)** | **S** | **Nízké** | **Střední** |
| **P2-4** | **Publish balíček: LICENSE, pyproject.toml, .gitignore ověření (kap. 9)** | **S** | **N/A** | **Vysoká — odemyká release** |

## P3 — nižší priorita / volitelné

| **Priorita** | **Položka** | **Náročnost** | **Snížení rizika** | **Hodnota** |
| - | - | - | - | - |
| **P3-1** | **MCP L3 Prompts (kap. 11.2)** | **M** | **Nízké** | **Nízká–střední** |
| **P3-2** | **Dockerfile (kap. 9.2)** | **M** | **Nízké** | **Střední** |
| **P3-3** | **Postupné rozšiřování FAKE\_ENGINEER\_KEYWORDS (F-12)** | **Průběžně malé kroky** | **Nízké** | **Nízká–střední** |
| **P3-4** | **Metrika četnosti selector-fallbacku (F-13)** | **S** | **Nízké** | **Nízká** |


# 13. Závěr a doporučení

linkedin-mcp-custom stojí na solidních architektonických základech — jasně oddělené scoring dimenze, čistý config systém, funkční graceful degradation a page pool management. Aktuální 92% chybovost běhu ale není jen provozní nepříjemnost: kapitola 2 ukazuje, že jde o souhru dvou příčin (pravděpodobné blokování ze strany LinkedInu + chybně ukotvený per-job timeout), z nichž druhá dosud nebyla v projektu identifikována. Kapitola 7 navíc odhalila konkrétní, číselně ověřitelnou nesrovnalost mezi vypočteným skóre a přiřazeným verdiktem, což je pro nástroj, jehož jediným účelem je důvěryhodné skórování, závažné zjištění samo o sobě.

Doporučený postup: dokončit čtyři položky P0 (kap. 12), spustit pipeline znovu proti živému LinkedInu a ověřit, že se úspěšnost blíží historickému 50/50 z běhu v 18:00. Teprve poté má smysl investovat do MCP L2–L4 rozvoje (kap. 11) a publish-readiness (kap. 9) — rozšiřovat funkčnost nebo komunitní dosah nástroje, který v 92 % případů neudělá to, k čemu je určen, by bylo předčasné a riskovalo by poškození reputace při prvním veřejném kontaktu.

Health Score 5/10 a podmíněné NE-GO doporučení z kapitoly 1 tak nejsou hodnocením architektury (ta je nadprůměrná pro pre-release nástroj jednoho vývojáře), ale hodnocením aktuální provozní spolehlivosti a nutnosti ověřit důvěryhodnost scoringové vrstvy dřív, než se na ni bude dál stavět.



*Konec zprávy. Vypracováno jako cross-LLM audit dle šablony MCP-Jobs audit\_prompt\_v1.1.docx, na základě commitu bd5b5dc a chybových dat běhu pipeline\_20260715\_194245.*
