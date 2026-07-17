# Kognitivní transfer: obscura → outpost2026

**Analýza přenosu tacitních znalostí z Rust projektu `h4ckf0r0day/obscura` (headless browser pro AI agenty a web scraping) do domény MCP serverů a pracovního portálového scrapingu**

> **⚠️ ZÁSADNÍ KOREKCE — PŘEČTI NEJPRVE**
>
> Tento dokument původně vznikl s předpokladem, že `samuelseidel/obscura` je Samuelův vlastní projekt. Detailní analýza odhalila:
> - `samuelseidel/obscura` je **fork** projektu `h4ckf0r0day/obscura` (19.3k ⭐, 302 commitů, 8+ contributorů)
> - Samuel Seidel má ve svém forku **přesně 1 vlastní commit** (POST/header options pro fetch)
> - Zbylých 39 commitů jsou upstream commity nebo PR od jiných lidí (mnaza, SGavrl, F0Rextasy, atd.)
> - Upstream už má vestavěný MCP server (`obscura mcp` s 11 nástroji), Docker image, a Obscura Cloud (komerční produkt)
> - Samuelův fork je 3 měsíce pozadu za upstreamem (v0.1.1 vs v0.1.10)
>
> **DŮSLEDEK:** Architektonická analýza kódu v sekcích 2-4 je **fakticky validní** (byla extrahována z kódu h4ckf0r0day/obscura, ne Samuelova forku). Ale atribuce autorství Samuelu Seidelovi je **nesprávná**. Patterny pochází od h4ckf0r0day teamu, ne od Samuela.
>
> Reference na Samuelovy další projekty (landomo-canada-realtor, eu-ai-act-legal-rag) zůstávají relevantní jako samostatný kontext.

Datum: 2026-07-17 (aktualizováno s korekcí autorství)
Kontext: Kazuistika — strukturální pattern matching mezi Rust-based headless browserem a TypeScript/Python MCP server architekturou
Klasifikace: INTERNAL — R&D know-how pro outpost2026

---

# 0. Kontext a motivace

Projekt `h4ckf0r0day/obscura` je open-source (Apache-2.0) headless browser napsaný v Rustu (forknut Samuelem Seidelem jako `samuelseidel/obscura`), který v praxi ověřuje tři klíčové principy relevantní pro tvoji MCP/scraping doménu:

1. **Workspace architektura s tvrdou separací vrstev** (7 crates: dom, net, js, browser, cdp, cli, mcp) — přesně to, co potřebuješ pro MCP server stack (domain, transport, tools, persistence, executor).
2. **CDP server (Chrome DevTools Protocol) jako interoperabilitní vrstva** — stejný princip jako MCP JSON-RPC: standardizovaný protokol, na který se napojuje libovolný klient (Playwright, Puppeteer, vlastní MCP klient).
3. **Pattern: orchestrace izolovaných worker procesů přes JSON-RPC stdin/stdout** — tentýž princip, který potřebuješ pro dlouhodobý scraping pracovních portálů (job-worker pattern, anti-ban izolace, crash recovery).

Používám kognitivní rámec z artefaktu `kognitivni*.md`:
- **Gentner (1983) structure-mapping**: přenos relační struktury, ne povrchových atributů
- **Holyoak & Thagard (1995) mental leaps**: tři faktory — podobnost, struktura, cíl
- **4 fáze externalizace tacitní znalosti**: signál → explorace → mapování → formalizace
- **Schraw (1998) metakognitivní monitoring**: feeling of knowing → explicitní extrakce

---

# 1. Tahle analýza v 4 fázích (artefakt kognitivni*.md, sekce 5.2)

## Fáze 1 — Signál

První setkání s `obscura` vyvolalo pattern matching na úrovni L2-L3 (artefakt kognitivni*.md, sekce 5.1):
- *„Fetch.{continue,fulfill,fail}Request"* → vlastní request interception ekvivalent
- *„RobotsCache s parsováním robots.txt"* → právní compliance pro pracovní portály (Jobs.cz, Profesia, atd.)
- *„CDP server na WebSocketu, HTTP endpointy /json/{version,list,protocol}"* → MCP server na stdio/HTTP s discovery endpointy
- *„Worker binary přes stdin/stdout JSON-RPC"* → izolace per-domain scraper procesů
- *„Tokio LocalSet kvůli !Send V8 runtime"* → izolace !Send (Python asyncio, Node child_process) v MCP tool handlerech

Tento signál byl tacitness — formalizace následuje.

## Fáze 2 — Explorace

Provedena systematická extrakce:
- 74+ souborů v 7 crates (zkopírovány do `/workspace/obscura-analysis/src/`)
- Commit historie upstreamu: **302 commitů**, hlavní vývoj: duben–červenec 2026, 8+ contributorů
- Repozitářová metadata upstreamu: **19 300 ⭐, 1 400 forků**, komerční produkt Obscura Cloud
- Commit historie Samuelova forku: 40 commitů, z toho **1 Samuelův** (POST/header options), zbytek synced upstream nebo cizí PR
- Repozitářová metadata forku: 0 hvězd, 0 forků, fork z `h4ckf0r0day/obscura` pořízen 27.4.2026
- Související repa Samuela Seidela: `landomo-canada-realtor` (TypeScript/Playwright, Phase 2 architektura), `eu-ai-act-legal-rag` (Python RAG s citation verification), `cybertruck-experience` (Next.js 16 demo)
- Referenční release workflow: upstream (multi-platform, 4 OS, stealth), fork (`v0.1.1-landomo.1` jen pro landomo)

## Fáze 3 — Mapování

Cross-domain mapování: Rust crates → MCP/TS komponenty (sekce 3 tohoto dokumentu).

## Fáze 4 — Formalizace

Tento dokument.

---

# 2. Architektura obscura — strukturální popis

## 2.1 Cargo workspace (7 crates, jasná separace concerns)

> **Poznámka:** Toto je struktura upstreamu `h4ckf0r0day/obscura` (v0.1.10). Samuelův fork (v0.1.1-landomo.1) chybí crates `obscura-mcp` a `obscura` — byl forknut v rané fázi a upstream mezitím přidal 2 nové crates + desítky commitů.

```
obscura/                                (workspace root)
├── crates/
│   ├── obscura-dom/                    DOM engine (parsing, tree, CSS selector)
│   │   ├── tree.rs                     548 řádků — Node tree s NodeId, parent/sibling/child linky
│   │   ├── selector.rs                 542 řádků — CSS selector engine přes Servo's `selectors` crate
│   │   ├── tree_sink.rs                100 řádků
│   │   ├── serialize.rs                56 řádků
│   │   └── lib.rs
│   │
│   ├── obscura-net/                    Síťová vrstva (HTTP, cookies, robots, interceptor)
│   │   ├── client.rs                   280 řádků — ObscuraHttpClient (reqwest-based, s policy)
│   │   ├── cookies.rs                  312 řádků — CookieJar s domain matching, expires, same-site
│   │   ├── robots.rs                   49 řádků — RobotsCache (parses robots.txt, in-memory)
│   │   ├── blocklist.rs                17 řádků — pgl_domains.txt (58KB tracker blocklist)
│   │   ├── interceptor.rs              33 řádků — async_trait RequestInterceptor + InterceptAction enum
│   │   └── lib.rs
│   │
│   ├── obscura-js/                     JavaScript runtime (V8 / deno_core)
│   │   ├── runtime.rs                  1329 řádků — ObscuraJsRuntime (snapshot + extensions)
│   │   ├── ops.rs                      245 řádků — Rust op bindings pro DOM/window/fetch
│   │   ├── module_loader.rs            27 řádků
│   │   ├── build.rs                    13 řádků — V8 snapshot path env var
│   │   └── js/bootstrap.js             134 628 bytů — celé DOM API implementované v JS nad Rust ops
│   │
│   ├── obscura-browser/                Orchestrace (Page, Context, Lifecycle)
│   │   ├── page.rs                     32 KB — Page struct, navigate, scripts execution
│   │   ├── context.rs                  60 řádků — BrowserContext (cookie_jar, http_client, robots_cache)
│   │   └── lifecycle.rs                20 řádků — LifecycleState + WaitUntil enum
│   │
│   ├── obscura-cdp/                    Chrome DevTools Protocol server
│   │   ├── server.rs                   27 KB — WebSocket server, request interception, network events
│   │   ├── dispatch.rs                 71 řádků — dispatch table (method → handler)
│   │   ├── domains/                    CDP domény: page, dom, network, runtime, fetch, ...
│   │   │   ├── page.rs                 167 řádků
│   │   │   ├── dom.rs                  92 řádků
│   │   │   ├── network.rs              34 řádků
│   │   │   ├── fetch.rs                61 řádků (request interception!)
│   │   │   ├── runtime.rs              85 řádků
│   │   │   ├── input.rs                80 řádků
│   │   │   ├── storage.rs              44 řádků
│   │   │   ├── target.rs               96 řádků
│   │   │   ├── accessibility.rs        146 řádků
│   │   │   ├── browser.rs              13 řádků
│   │   │   ├── lp.rs                   37 řádků
│   │   │   └── mod.rs
│   │   ├── types.rs                    18 řádků — CdpRequest/Response/Event
│   │   └── lib.rs
│   │
│   ├── obscura-mcp/                    ⬅️ CHYBÍ V SAMUELOVĚ FORKU — MCP server (11 nástrojů)
│   │
│   ├── obscura/                        ⬅️ CHYBÍ V SAMUELOVĚ FORKU — embeddable Rust lib API
│   │
│   └── obscura-cli/                    Binárka (fetch, serve, scrape, worker, mcp)
│       ├── main.rs                     26 KB — clap subcommands: serve/fetch/scrape/mcp
│       └── worker.rs                   45 řádků — standalone worker přes stdin/stdout JSON-RPC
│
├── docs/                               ⬅️ CHYBÍ V SAMUELOVĚ FORKU — dokumentace
├── skills/obscura/                     ⬅️ CHYBÍ V SAMUELOVĚ FORKU — MCP skill pro AI agenty
└── .github/workflows/release.yml       Multi-platform release (Linux/macOS/Windows)
```

## 2.2 Klíčové design decisions (extrakce ze zdrojáků)

### A. Workspace pattern: 5 crate monorepo, workspace-level dependencies

```toml
# Cargo.toml (root)
[workspace]
resolver = "2"
members = [
    "crates/obscura-dom",
    "crates/obscura-net",
    "crates/obscura-browser",
    "crates/obscura-cdp",
    "crates/obscura-js",
    "crates/obscura-cli",
]

[workspace.dependencies]
# Všechny crates sdílejí ty samé verze
html5ever = "0.29"
reqwest = { version = "0.12", features = ["cookies", "gzip", "brotli", "deflate", "native-tls-vendored"], default-features = false }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
```

**Proč je to důležité pro tebe**: MCP servery a scraping nástroje trpí na dependency drift mezi moduly. Workspace pattern explicitně řeší verzování.

### B. `BrowserContext` jako Arc-wrappovaný sdílený stav

```rust
pub struct BrowserContext {
    pub id: String,
    pub cookie_jar: Arc<CookieJar>,           // Sdíleno mezi všemi pages
    pub http_client: Arc<ObscuraHttpClient>,  // Sdíleno mezi všemi pages
    pub user_agent: String,
    pub proxy_url: Option<String>,
    pub robots_cache: Arc<RobotsCache>,       // Sdíleno
    pub obey_robots: bool,
    pub stealth: bool,
}
```

**Pattern**: Context = životní prostředí (cookies, auth, proxy, robots politika). Page = jednotlivá stránka v daném contextu. Stejný context může mít N pages (paralelní taby v browseru).

**Pro tebe**: `McpContext` = session state (auth tokens, rate limit, schema cache). `ToolHandler` = jeden tool běžící v contextu. Context se předává Arc, handlery se klonují.

### C. Lifecycle state machine s `WaitUntil` semantikou

```rust
pub enum LifecycleState { Idle, Loading, DomContentLoaded, Loaded, NetworkIdle, Failed }
pub enum WaitUntil { Load, DomContentLoaded, NetworkIdle0, NetworkIdle2 }
```

`WaitUntil::from_str("networkidle2")` parsuje string → enum → orchestration logic. **Pattern**: Naming, ne magie. Klienti vždy znají všechna platná slova.

### D. Page navigation jako coroutine s network event capture

```rust
// page.rs (zkráceno)
pub struct Page {
    pub id: String,
    pub frame_id: String,                    // Chromiová konvence: main frameId == targetId
    pub url: Option<Url>,
    pub dom: Option<DomTree>,
    pub js: Option<ObscuraJsRuntime>,
    pub lifecycle: LifecycleState,
    pub http_client: Arc<ObscuraHttpClient>,
    pub context: Arc<BrowserContext>,
    pub title: String,
    pub network_events: Vec<NetworkEvent>,   // Všechny request/response během navigace
    network_event_counter: u32,
    pub intercept_enabled: bool,
    pub intercept_block_patterns: Vec<String>,  // Glob-style patterns
    intercept_tx: Option<mpsc::UnboundedSender<InterceptedRequest>>,
}
```

Frame id convention: `let frame_id = id.clone();` — to je **záměrné**! Komentář v kódu explicitně říká, že Playwright očekává tuto konvenci. **Pattern**: dokumentuj konvence, i když vypadají jako implementační detail.

### E. Tokio LocalSet, ne plný async runtime

```rust
// cdp/server.rs
let local = tokio::task::LocalSet::new();
local.run_until(async {
    // Všichni spawned tasks běží na stejném threadu (!Send types)
    let processor_handle = tokio::task::spawn_local(cdp_processor(msg_rx, ...));
    ...
}).await
```

**Proč**: V8 runtime (deno_core) je !Send. LocalSet umožňuje async bez cross-thread requirements. **Pattern pro tebe**: Pokud používáš Python asyncio + subprocess, izoluj !Send (file handles, locks) do jednoho tasku; pro paralelní zpracování použij multiprocessing ne multithreading.

### F. `async_trait` interceptor pattern

```rust
// net/interceptor.rs
pub enum InterceptAction { Continue, Block, Fulfill(Response), ModifyHeaders(HashMap<String, String>) }

#[async_trait::async_trait]
pub trait RequestInterceptor {
    async fn intercept(&self, request: &RequestInfo) -> InterceptAction;
}
```

**Pattern**: Pluggable behavior přes trait object. RequestInterceptor se dá vložit do `ObscuraHttpClient.interceptor: RwLock<Option<Box<dyn RequestInterceptor + Send + Sync>>>`. Víc interceptorů se řetězí.

**Pro tebe**: McpToolInterceptor — middlewarová pipeline (auth, rate limit, audit, transform).

### G. Multi-worker serve s round-robin load balancerem

```rust
// cli/main.rs (zkráceno)
async fn run_multi_worker_serve(port: u16, workers: u16, ...) {
    for i in 0..workers {
        let worker_port = port + 1 + i;
        let mut cmd = std::process::Command::new(&exe);
        cmd.arg("serve").arg("--port").arg(worker_port.to_string());
        // ... spawn worker process
    }
    // Parent: TCP listener na `port`, round-robin přeposílá na worker_port
}
```

**Pattern**: parent = load balancer, N workers = workery. Každý worker má vlastní port (parent_port+1, +2, ...). JSON-RPC discovery endpoint `/json/list` se routuje na aktuální worker, ne na parent.

### H. Worker přes stdin/stdout JSON-RPC

```rust
// cli/main.rs (run_parallel_scrape, zkráceno)
let mut child = TokioCommand::new(worker_path)
    .stdin(Stdio::piped())
    .stdout(Stdio::piped())
    .spawn()?;

// Protocol:
let nav_cmd = serde_json::json!({"cmd": "navigate", "url": url});
stdin.write_all((serde_json::to_string(&nav_cmd).unwrap() + "\n").as_bytes()).await?;
// Read response:
let mut resp_line = String::new();
reader.read_line(&mut resp_line).await?;

let eval_cmd = serde_json::json!({"cmd": "evaluate", "expression": expr});
// ...

let shutdown_cmd = serde_json::json!({"cmd": "shutdown"});
// ...
```

**Pattern**: Žádný HTTP, žádný gRPC. Plain JSON-RPC přes pipe. Worker dostane `navigate` → `evaluate` → `shutdown`. **Process isolation = crash safety**. Pokud worker crashne, parent může snadno respawnout.

**Pro tebe**: Toto je **přesně** pattern, který potřebuješ pro per-portál scraper workery. Každý portál = 1 worker process, JSON-RPC přes pipe, parent scheduler dispatchuje joby.

### I. CDP event ordering — kritické pro Playwright

```rust
// cdp/server.rs, process_cdp_message
let response = dispatch::dispatch(&req, ctx).await;

// Chromium CDP semantics: events emitted as a side-effect of a command
// (e.g. Target.targetCreated + Target.attachedToTarget from
// Target.createTarget) MUST arrive BEFORE the command's response.
// Playwright awaits the response and immediately reads state wired up
// by those events; if the response lands first, accessing
// Target._page errors with "Cannot read properties of undefined".
for event in ctx.pending_events.drain(..) {
    let _ = reply_tx.send(/* serialized event */);
}
// THEN send response
let _ = reply_tx.send(/* response */);
```

**Pattern**: U protokolů s event streamem (CDP, MCP, SSE) je pořadí zpráv klíčové. Implementátoři specifikace často dokumentují jen stavový diagram, ale **temporální invarianty** jsou stejně důležité.

### J. Fast-path responses pro neimplementované CDP metody

```rust
// cdp/server.rs
fn fast_path_response(text: &str) -> Option<String> {
    let req: CdpRequest = serde_json::from_str(text).ok()?;
    let result = match req.method.as_str() {
        "Network.enable" | "Network.setCacheDisabled" | ... => Some(json!({})),
        "Browser.getVersion" => Some(json!({
            "protocolVersion": "1.3",
            "product": "Obscura/0.1.0",
            "userAgent": "Obscura/0.1.0",
            "jsVersion": "V8",
        })),
        _ => None,
    };
    ...
}
```

**Pattern**: I když něco plně neimplementuješ, **vrať valid response na no-op**, aby klient (Playwright) nepadl. Toto je **graceful degradation** na úrovni protokolu.

**Pro tebe**: Pokud tvůj MCP server nemá tool X, nevracej chybu, ale `{"result": null}` nebo `{"tools": []}`. Klienti (Claude, GPT) se s tím vyrovnají.

### K. Stealth jako Cargo feature flag, ne vlastní binary

```toml
# crates/obscura-net/Cargo.toml
[features]
default = []
stealth = ["wreq", "wreq-util"]

# crates/obscura-browser/Cargo.toml
[features]
default = []
stealth = ["obscura-net/stealth"]

# crates/obscura-cli/Cargo.toml
[features]
default = []
stealth = ["obscura-browser/stealth", "obscura-net/stealth"]
```

```bash
cargo build --release                      # bez stealthu
cargo build --release --features stealth   # s TLS fingerprint impersonation
```

Stealth přepne z `reqwest` (TLS fingerprint = OpenSSL/rustls) na `wreq` (curl-impersonate based, fingerprint = Chrome/Firefox/Safari). **Pattern**: volitelná funkcionalita, ne duální build.

### L. Bootstrap.js — celé DOM API jako JS nad Rust ops

`obscura-js/js/bootstrap.js` = **134 628 bytů** monolitického JS, který implementuje `document`, `window`, `navigator`, `Element`, `Node`, `Event`, `fetch`, `localStorage` atd. — to vše nad Rust ops (`ops.rs`, 245 řádků).

**Pattern**: Move as much as possible do JS (DOM, queryselector, regex), Rust poskytuje jen I/O + low-level ops. JS je mnohem rychlejší na prototypování UI-level API.

### M. Multi-platform release s glibc pinning

```yaml
# .github/workflows/release.yml
- target: x86_64-unknown-linux-gnu
  os: ubuntu-22.04   # explicitní glibc 2.35 target
- target: aarch64-apple-darwin
  os: macos-latest
- target: x86_64-apple-darwin
  os: macos-13       # pinned kvůli kompatibilitě
- target: x86_64-pc-windows-msvc
  os: windows-latest
```

```bash
# Build stealth = continue-on-error
- name: Build stealth
  run: cargo build --release --target ${{ matrix.target }} --features stealth
  continue-on-error: true
```

**Pattern**: Pokud máš experimental feature (stealth), nech CI ji zkusit, ale nefailuj buildu. Release artifacts můžou být jak s, tak bez.

### N. Bezpečnost: blokace privátních IP a file://

```rust
// net/client.rs
fn validate_url(url: &Url) -> Result<(), ObscuraNetError> {
    if scheme != "http" && scheme != "https" && scheme != "file" {
        return Err(...);
    }
    if let Some(host) = url.host() {
        match host {
            url::Host::Ipv4(ip) => {
                if ip.is_loopback() || ip.is_private() || ip.is_link_local()
                   || ip.is_broadcast() || ip.is_documentation() {
                    return Err(...);  // SSRF prevence!
                }
            }
            // ...
        }
    }
    Ok(())
}
```

**Pattern**: Vestavěná SSRF prevence. Pokud tvůj MCP server umožní fetch URL, vždy validuj proti private/loopback rozsahům.

### O. Cookie management — plně implementovaný standard

`obscura-net/cookies.rs` (312 řádků) implementuje:
- `Set-Cookie` parsing s Domain/Path/Secure/HttpOnly/Expires/Max-Age/SameSite
- Domain matching (subdomain support)
- Path prefix matching
- Expiry check
- HttpOnly filtr pro `get_cookie_header` (odesílá) vs `get_js_visible_cookies` (pro JS kontext)
- `set_cookies_from_cdp` — import z CDP Network.cookie事件

**Pro tebe**: Pokud scrapuješ portály s auth (LinkedIn, Jobs.cz s přihlášením), potřebuješ vlastní cookie jar. Knihovna `cookie_store` v Rustu, `tough-cookie` v Node.js, `requests` v Pythonu — ale **vždy implementuj Domain matching správně** (subdoména vs parent domain).

### P. Robots.txt cache

```rust
// net/robots.rs
pub struct RobotsCache {
    cache: RwLock<HashMap<String, RobotsRules>>,
}

pub fn parse_robots_txt(body: &str, our_agent: &str) -> RobotsRules {
    // 1. Najdi specifický user-agent match
    // 2. Fallback na User-agent: *
    // Podporuje: Allow, Disallow, * wildcards, $ end-anchor
}
```

**Pattern**: Vestavěná právní compliance. Pokud scrapuješ veřejné portály, `RobotsCache.is_allowed(domain, path)` by měl být tvůj první guard. Pro interní API (LinkedIn, Jobs.cz backend) irelevantní; pro veřejné weby nutné.

---

# 3. Cross-domain mapování (artefakt kognitivni*.md, sekce 3.4)

## 3.1 Strukturální equvivalence: obscura crates ↔ MCP/Scraping stack

| **obscura crate** | **Funkce** | **outpost2026 ekvivalent** | **Přenositelnost** |
|---|---|---|---|
| `obscura-dom` | HTML parsing, CSS selector, tree | `scraper-core/extract` (BS4/Playwright/lxml wrapper) | Přímý — parsování je stejné |
| `obscura-net` | HTTP client, cookies, robots, interceptor | `scraper-core/net` (httpx + cookie store + robots) | Přímý |
| `obscura-js` | V8 runtime, JS execution | `mcp-runtime` (Pyppeteer/Playwright wrapper) | Částečný — JS exec je pomalejší v Pythonu |
| `obscura-browser` | Page orchestration, lifecycle | `mcp-core/session` (Page abstraction) | Přímý |
| `obscura-cdp` | CDP server, request interception | `mcp-server/protocol` (JSON-RPC server + middleware) | **Největší value** — pattern přenositelný 1:1 |
| `obscura-cli` | CLI subcommands: serve/fetch/scrape | `outpost2026 CLI` (mcp-server / scrape / analyze) | Přímý |
| `bootstrap.js` (134KB) | DOM API v JS nad Rust ops | TypeScript decorators pro Playwright/BS4 hybrid | Částečný |
| Multi-worker serve | Process isolation + load balancer | Per-portál worker processes | **Největší value** |
| Worker stdin/stdout JSON-RPC | Inter-process protocol | Job dispatch protocol | **Největší value** |
| `BrowserContext` (Arc) | Sdílený state across pages | `McpContext` (auth, rate limit, schema) | Přímý |
| `Page.network_events` | Capture all HTTP během navigace | `RequestTrace` (všechny requesty v rámci tasku) | Přímý |
| `RequestInterceptor` trait | Pluggable HTTP middleware | `McpToolMiddleware` | Přímý |
| `CookieJar` | Domain-matched cookie storage | `cookie_store` nebo vlastní | Přímý |
| `RobotsCache` | robots.txt parser + cache | `reppy` nebo `urllib.robotparser` | Přímý |
| `validate_url` | SSRF prevence | Must-have pro všechny MCP fetch nástroje | Přímý |
| Fast-path CDP responses | Graceful degradation | Empty/no-op MCP tool responses | Přímý |
| `WaitUntil` enum | Named lifecycle states | MCP tool timeout/state semantics | Přímý |
| `cargo --features stealth` | Volitelná funkcionalita | `pip install outpost2026[stealth]` | Přímý |
| GitHub Actions matrix release | Multi-platform | GitHub Actions matrix pro PyPI/wheel | Přímý |
| Frame ID == Page ID konvence | Client compat invariant | Tool name == endpoint name | Přímý (ale snadno přehlédnutelné) |

## 3.2 Mentální model: 4-fázový externalizační protokol

Mapování na tvoji MCP/LinkedIn/Jobs.cz doménu:

**Fáze A — Signál** (uznej, že pattern existuje)
- Když píšeš nový MCP tool, cítíš „tohle je jako ta CDP dispatch tabulka" → zapiš si to
- Když přidáváš nový portál scraper, cítíš „tohle je jako worker process" → ulož do backlogu

**Fáze B — Struktura** (identifikuj invarianty)
- Invarianty: process isolation, JSON-RPC, dispatcher, context, request capture, cookies, robots
- Povrch: Rust vs Python, V8 vs CPython, cargo vs uv

**Fáze C — Mapování** (vytvoř equvivalenční tabulku jako v sekci 3.1)
- Pro každý obscura pattern najdi outpost2026 ekvivalent
- Pokud ekvivalent neexistuje, rozhodni: vytvoř, přeskoč, nebo přizpůsob

**Fáze D — Formalizace** (dokumentuj, implementuj, validuj)
- Tento dokument je fáze D
- Implementace patternů je iterativní — viz sekce 6 (Roadmap)

## 3.3 Konkrétní mapování na tvoje 3 use casy

### A. MCP server builder (`outpost2026/linkedin-mcp-analyzer`)

| **obscura** | **linkedin-mcp-analyzer** | **Akce** |
|---|---|---|
| `obscura-cdp/server.rs` — WebSocket server s discovery | MCP server přes stdio/HTTP s `tools/list` | Refaktoruj na ten samý pattern: dispatcher tabulka + fast-path no-op responses |
| `BrowserContext` — Arc-wrappovaný state | LinkedIn session (cookies, headers, rate limit) | Zapouzdři do `LinkedInContext: Arc<...>` |
| `Page.network_events` | Trace všech LinkedIn requestů v rámci tool volání | Přidej `RequestTrace` strukturu |
| CDP `Fetch.{continue,fulfill,fail}Request` | LinkedIn anti-bot bypass (rate limit, auth challenge) | Implementuj jako `Interceptor` middleware |
| `WaitUntil::NetworkIdle0` | Čekání na dokončení LinkedIn async load | Explicitní `ToolState` enum |
| `serve` subcommand | `mcp-server` subcommand | 1:1 přenos |
| `fetch --eval` | `linkedin-analyzer get-profile` | 1:1 přenos |

### B. Scraping pracovních portálů (Jobs.cz, Profesia, atd.)

| **obscura** | **Pracovní portály** | **Akce** |
|---|---|---|
| `landomo-canada-realtor` (Phase 2 architektura) | Tvůj plánovaný multi-portál scraper | Přesně stejný pattern: Coordinator + Workers + Verifier |
| Worker process přes stdin/stdout JSON-RPC | Per-portál worker (Jobs.cz, Profesia, StartupJobs) | **Přesně to** co Samuel Seidel dělá pro realitní portály |
| Redis queue (landomo-canada-realtor) | Job queue | `rq` nebo `arq` v Pythonu |
| PostgreSQL snapshots + change tracking | Snapshot + change tracking | `sqlalchemy` + `asyncpg` |
| Prometheus metrics | Worker performance | `prometheus-client` |
| Adaptive scheduling (2h-24h) | Per-portál poll frequency | `apscheduler` |
| `RobotsCache` | Portál Terms of Service checker | **Vytvoř vlastní `TermsOfServiceCache`** — viz sekce 5.4 |
| Anti-bot detection (stealth mode) | LinkedIn / Jobs.cz anti-scraping | `playwright-stealth` + `curl_cffi` |
| Multi-region domén (30+ jazyků) | N portálů v různých zemích | Per-locale worker |
| Geo-grid (1° × 1° Kanada) | Geo-grid pro pokrytí celé země | Parametrizovatelný grid |

### C. Aspirational adoption (další projekty)

| **obscura** | **Aspirace** | **Poznámka** |
|---|---|---|
| Workspace monorepo (5 crates) | Tvoje portfolio monorepo | `outpost2026` jako GitHub org s N repy |
| `obscura-dom` je `private` reusable crate | `outpost2026/core` sdílená knihovna | Vlastní PyPI/uv workspace |
| `obscura-cli` distribuuje binárku | `outpost2026` CLI nástroj | `pipx install outpost2026` |
| Multi-platform release | Cross-platform wheel | cibuildwheel / maturin |

---

# 4. Přenositelné patterny (top 12, ověřeno na zdrojácích)

## 4.1 **Workspace monorepo s workspace-level dependencies**

**Proč**: Konzistentní verze napříč moduly, atomické releasy, snadná refaktorizace napříč crate boundaries.

**Implementace pro tebe**: Přesuň `outpost2026` z jednoho repa na GitHub org + N repa s vlastním CI. Např.:
```
outpost2026/
├── core/             # Sdílené utility (parsování, validace, storage)
├── net/              # HTTP klient + cookies + robots + interceptor
├── browser/          # Playwright wrapper s context/page abstraction
├── mcp-protocol/     # JSON-RPC server s discovery
├── linkedin-mcp/     # LinkedIn-specifické nástroje
├── jobs-cz-mcp/      # Jobs.cz-specifické nástroje
└── cli/              # Entry point
```

Případně: `uv workspace` (Python) nebo `pnpm workspace` (TypeScript).

## 4.2 **CDP-style discovery endpoint**

**Proč**: Klienti (Playwright, ale i tvůj vlastní test harness) mohou auto-detectovat server, verzi, capabilities.

**Implementace pro tebe**: MCP server by měl odpovídat na:
- `tools/list` (ekvivalent CDP `Target.getTargets`)
- `server/info` (ekvivalent CDP `Browser.getVersion`)
- `health/check` (ekvivalent CDP `Browser.getVersion` health check)

## 4.3 **Fast-path no-op responses pro neimplementované metody**

**Proč**: Graceful degradation, klient nepadá, server může přidávat features iterativně.

**Implementace pro tebe**: `MCP_NOOP_METHODS = {"prompts/list": {"prompts": []}, "resources/list": {"resources": []}, ...}`. Pokud tvůj MCP server neimplementuje prompts/resources, ale klient se ptá, vrať validní prázdnou odpověď.

## 4.4 **BrowserContext pattern (Arc-wrappovaný state)**

**Proč**: Sdílení state mezi paralelními pages/requests bez lock contention.

**Implementace pro tebe**:
```python
@dataclass
class ScraperContext:
    cookies: CookieJar
    http_client: httpx.AsyncClient
    rate_limiter: AsyncLimiter
    user_agent: str
    proxy: Optional[str]
    robots_cache: dict[str, RobotsRules]
    
# Použití:
ctx = ScraperContext(...)
page1 = await ctx.new_page(url)  # Sdílí cookies/http/rate_limit
page2 = await ctx.new_page(url)  # Sdílí
```

## 4.5 **Async trait interceptor pattern**

**Proč**: Middlewarová pipeline (auth, rate limit, audit, transform, retry) bez duplikace.

**Implementace pro tebe**:
```python
class RequestInterceptor(Protocol):
    async def intercept(self, request: RequestInfo) -> InterceptAction: ...

# Použití:
client = ObscuraHttpClient(
    interceptors=[
        RateLimitInterceptor(10, per=60),
        AuthInterceptor(token),
        RetryInterceptor(max_retries=3),
        AuditInterceptor(callback),
    ]
)
```

## 4.6 **Worker process isolation přes JSON-RPC stdin/stdout**

**Proč**: Process isolation = crash safety. Žádný shared memory, žádné locky. Pipe = standard.

**Implementace pro tebe**:
```python
# Worker:
async def worker_main():
    while True:
        line = sys.stdin.readline()
        cmd = json.loads(line)
        if cmd["cmd"] == "scrape":
            result = await scrape(cmd["url"])
            print(json.dumps({"ok": True, "result": result}), flush=True)
        elif cmd["cmd"] == "shutdown":
            break

# Parent:
async def dispatch(url):
    proc = await asyncio.create_subprocess_exec(...)
    proc.stdin.write(json.dumps({"cmd": "scrape", "url": url}).encode() + b"\n")
    line = await proc.stdout.readline()
    return json.loads(line)
```

## 4.7 **Multi-process load balancer s round-robin**

**Proč**: Horizontální škálování bez threadů, maximální crash safety, jednoduchý deployment.

**Implementace pro tebe**: 
- `mcp-coordinator` (parent): TCP/stdio listener, round-robin dispatch na N workerů
- `mcp-worker-1`, `mcp-worker-2`, ...: izolované procesy

## 4.8 **Tokio LocalSet pro !Send types**

**Proč**: V8 runtime (deno_core), ale i Python asyncio file handles / SQLite connections jsou !Send. LocalSet umožňuje async bez cross-thread.

**Implementace pro tebe**: 
- Pro MCP tool handlery: 1 asyncio loop per tool invocation
- Pro Playwright: subprocess per page (Playwright je !Send napříč pages)
- Pro SQLite: `aiosqlite` (single connection per process, ne per task)

## 4.9 **Feature flag pattern pro volitelné chování**

**Proč**: 
- Anti-bot stealth není vždy potřeba (a často porušuje ToS)
- Debug logy ne vždy
- Experimentální features ne vždy

**Implementace pro tebe**:
```python
# pyproject.toml
[project.optional-dependencies]
stealth = ["playwright-stealth", "curl_cffi"]
debug = ["icecream"]
experimental = ["playwright-stealth", "scrapy", "arxiv"]

# main.py
if os.getenv("OUTPOST2026_STEALTH"):
    from outpost2026.stealth import apply_stealth
    apply_stealth()
```

## 4.10 **Multi-platform release s glibc pinning (pro Rust) / cibuildwheel (pro Python)**

**Proč**: Cross-platform konzistence.

**Implementace pro tebe**:
- Python: `cibuildwheel` pro wheel distribuci (Linux/macOS/Windows, manylinux PEP 600)
- TypeScript: `vercel/ncc` nebo `tsc --build` pro ESM/CJS dual
- Rust: GitHub Actions matrix s pinned Ubuntu 22.04

## 4.11 **Vestavěná SSRF prevence**

**Proč**: Pokud tvůj MCP server má `fetch` nebo `http_request` tool, je to okamžitý bezpečnostní incident.

**Implementace pro tebe**: Přidej `validate_url()` jako **první** guard:
```python
ALLOWED_SCHEMES = {"http", "https", "file"}
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]

def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise SSRFError(f"Scheme {parsed.scheme} not allowed")
    # Resolve DNS a zkontroluj IP
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise SSRFError("DNS resolution failed")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in PRIVATE_IP_RANGES):
            raise SSRFError(f"Private IP {ip} not allowed")
```

## 4.12 **Právní compliance vestavěná do sítě (RobotsCache)**

**Proč**: Pokud scrapuješ veřejné portály, `robots.txt` je de facto standard. Interní API portálů (LinkedIn, Jobs.cz API) mají ToS, ne robots.txt.

**Implementace pro tebe**:
- Vestavěný `RobotsCache` s parsováním a cachováním
- Default: `obey_robots = true` (vždy)
- Per-portál override: `obey_robots = false` (pokud máš smluvní API přístup)
- Audit log: který path byl blokován, kdy, proč

**Důležitá nuance pro tebe**: Pro scraping pracovních portálů typu Jobs.cz je `robots.txt` irelevantní — ty scrapuješ **interní API portálu**, ne veřejné stránky. Ale pro doplňkové veřejné zdroje (např. startupdirectory.cz) je to relevantní.

---

# 5. Anti-patterny a úskalí (z observace obscura)

## 5.1 Commit historie ukazuje iterativní opravy (ne čistý design)

Upstream `h4ckf0r0day/obscura` má **302 commitů** (duben–červenec 2026), 8+ contributorů, aktivní vývoj s pravidelnými releasy (v0.1.0 – v0.1.10). Příklady upstream commitů:
- `fix(js): structuredClone cycles through Error.cause` (mnaza, SGavrl)
- `fix(net): scope passive callbacks to the registering page` (BrandNewJimZhang)
- `fix(js): expose Document.adoptNode and Element.toggleAttribute` (BrandNewJimZhang)
- `fix(cdp): prune valid_context_ids on executionContextsCleared` (SGavrl)
- `fix(cdp): bound DOM.getDocument depth so deep DOMs cannot crash the worker` (mnaza)
- `feat(cdp): implement Accessibility domain (getFullAXTree)` (zhangyang-crazy-one)
- `feat(cdp): stream large response bodies via takeResponseBodyAsStream + IO` (SGavrl)
- `fix(cli): pass worker proxy via env, not argv (credential leak)` (SGavrl)

Samuelův fork má **40 commitů** (fork z 27.4.2026, 1 vlastní commit + 39 synced upstream). Jeho jediný vlastní commit:
- `Add fetch POST and header options` (387c614)

**Pattern**: Žádný software není "hotový". Upstream ukazuje, že kvalitní projekt vyžaduje stovky iterací a tým contributorů. **Pro tebe**: plánuj alespoň 4-6 iterací, než budeš mít Playwright/Claude/GPT všechny spokojené.

## 5.2 "Stealth" je feature flag, nikdy ne default

`stealth` je **opt-in** v obscura. README explicitně říká: *„Stealth mode enabled (TLS fingerprint impersonation + tracker blocking)"*. **Pattern**: Anti-bot je experimentální, nespolehlivý, často porušuje ToS. Nikdy by neměl být default.

**Pro tebe**: 
- `outpost2026[stealth]` = opt-in
- Default: legitimní HTTP klient s realistickými headery
- Anti-bot jen když klient explicitně řekne (a ideálně má právní krytí)

## 5.3 Bootstrap.js = 134KB monolit

To je **technický dluh**. Celé DOM API je v jednom souboru, neexistuje modularita. Splňuje to, ale neumožňuje to evoluci.

**Pattern**: U prototypu je monolit OK. U produkčního kódu rozděl na moduly. **Pro tebe**: Tvoje MCP nástroje by měly být modulární od začátku — `outpost2026/tools/linkedin/`, `outpost2026/tools/jobs/`, atd.

## 5.4 Vlastní enkodér na CPU

Samuel Seidel ve FB příspěvku tvrdí: *„nyní testuji vlastní enkodér, který dokáže běžet čistě na CPU"*. Toto je **opakovaný pattern u indie AI vývojářů** — trénovat vlastní model místo použití API. **Doporučení**: Nedělej to, dokud nemáš validovaný use case. API (OpenAI, Anthropic, Mistral) je 100× levnější než vlastní inference, pokud neškálouješ na >10M requestů/měsíc.

---

# 6. Roadmap adoptce pro outpost2026

## 6.1 Fáze 1: Příprava (1-2 týdny)

- [ ] Přečti znovu tento dokument + kognitivní artefakt
- [ ] Inventarizuj existující repozitáře outpost2026
- [ ] Rozhodni: monorepo (uv workspace) vs. polyrepo (GitHub org)
- [ ] Vytvoř `/workspace/outpost2026-architecture.md` se stejnou strukturou jako tento dokument (5 crate ekvivalent)

## 6.2 Fáze 2: Core extrakce (2-3 týdny)

- [ ] `outpost2026/core` — společné utility (logger, config, errors)
- [ ] `outpost2026/net` — HTTP klient + cookies + robots + interceptor
- [ ] `outpost2026/browser` — Playwright wrapper s context/page abstraction
- [ ] `outpost2026/protocol` — JSON-RPC server s discovery
- [ ] `outpost2026/cli` — entry point

## 6.3 Fáze 3: První use case (3-4 týdny)

- [ ] `outpost2026/mcp/linkedin` — port existujícího linkedin-mcp-analyzeru
- [ ] Aplikuj Context pattern, RequestInterceptor, JSON-RPC dispatcher
- [ ] Přidej `validate_url` SSRF guard
- [ ] Test s Claude/GPT jako MCP klientem
- [ ] Dokumentuj 3-5 největších lesson learned

## 6.4 Fáze 4: Škálování (4-6 týdnů)

- [ ] `outpost2026/mcp/jobs-cz` — první pracovní portál
- [ ] `outpost2026/mcp/profesia` — druhý portál (pro srovnání)
- [ ] `outpost2026/scraper/orchestrator` — Phase 2 architektura (Coordinator + Workers + Verifier) z landomo-canada-realtor
- [ ] Redis queue (`arq` nebo `rq`)
- [ ] PostgreSQL snapshots (`sqlalchemy` + `asyncpg`)
- [ ] Prometheus metrics
- [ ] Multi-worker process orchestration

## 6.5 Fáze 5: Distribuce (ongoing)

- [ ] `cibuildwheel` pro multi-platform wheel
- [ ] Docker image pro orchestrator + workery
- [ ] GitHub Actions matrix release
- [ ] Landing page s demo
- [ ] Blog post: "Jak jsme postavili MCP server stack inspirovaný obscura"

---

# 7. Konkrétní implementační TODO (next 7 dní)

## 7.1 Rychlé wins (1-2 dny)

1. **Přidej `validate_url` do všech MCP toolů, které berou URL**
   ```python
   # outpost2026/util/ssrf.py
   def validate_url(url: str, allow_private: bool = False) -> None:
       """SSRF prevence. raise SSRFError pokud URL je na privátní IP."""
       ...
   ```

2. **Přidej `RobotsCache` wrapper**
   ```python
   # outpost2026/util/robots.py
   class RobotsCache:
       def __init__(self, user_agent: str, obey: bool = True): ...
       async def is_allowed(self, url: str) -> bool: ...
   ```

3. **Vytvoř `RequestInterceptor` protocol + 2 implementace**
   ```python
   # outpost2026/net/interceptor.py
   class RequestInterceptor(Protocol):
       async def before_request(self, req: RequestInfo) -> RequestInfo: ...
       async def after_response(self, req: RequestInfo, resp: Response) -> Response: ...
   
   class RateLimitInterceptor: ...
   class AuditInterceptor: ...
   ```

## 7.2 Střední wins (3-5 dní)

4. **Refaktoruj `linkedin-mcp-analyzer` na Context pattern**
   - Zapouzdři cookies + http client + rate limit do `LinkedInContext`
   - Přidej `RequestTrace` pro capture všech requestů v rámci tool volání

5. **Vytvoř `outpost2026-mcp-core` balíček**
   - JSON-RPC server s discovery
   - Fast-path no-op responses
   - Middleware pipeline (RequestInterceptor chain)

6. **Přidej CI s multi-platform testy**
   - GitHub Actions matrix: Ubuntu + macOS + Windows
   - `pytest` + `playwright install` cache
   - Coverage reporting

## 7.3 Dlouhodobé (1-2 týdny)

7. **Implementuj worker process orchestration**
   - Parent: TCP/stdio listener + round-robin dispatcher
   - Worker: stdin/stdout JSON-RPC
   - Per-portál worker (LinkedIn, Jobs.cz, Profesia)

8. **Přidej Adaptive Scheduling (jako landomo-canada-realtor)**
   - Per-portál poll frequency (2h-24h)
   - High-change property prioritization
   - Distributed locking přes Redis

9. **Vytvoř `outpost2026/scraper/orchestrator` jako Phase 2 architektura**
   - Coordinator (discovery)
   - Workers (processing)
   - Verifier (missing property detection)
   - Metrics (Prometheus)

---

# 8. Rizika a limitace

## 8.1 Právní rizika

- **Scraping pracovních portálů (Jobs.cz, Profesia) je v rozporu s jejich ToS** — i když máš robota, který ctí robots.txt. Většina portálů má v ToS explicitní zákaz scrapingu pro komerční účely.
- **LinkedIn aktivně žaluje scrapery** (HiQ Labs vs. LinkedIn, 2019 — Nejvyšší soud USA rozhodl ve prospěch HiQ, ale v EU je situace odlišná, GDPR přidává další omezení).
- **GDPR**: Osobní údaje v inzerátech (jména, kontakty) podléhají GDPR. Jejich sběr a zpracování vyžaduje právní základ (souhlas, oprávněný zájem, smlouva).
- **Doporučení**: Pokud je to jen pro osobní použití, riziko je nízké. Pokud pro komerční, **poraď se s právníkem specializovaným na IT/AI/GDPR**.

## 8.2 Technická rizika

- **Bot detection**: I s `playwright-stealth` tě Sreality.cz, Jobs.cz, LinkedIn mohou detekovat. Průběžná údržba.
- **Schema changes**: Každá změna HTML/API pracovního portálu = nový scraper nebo update.
- **Rate limiting**: Příliš rychlé requesty = ban. Potřeba adaptivní throttle.
- **CAPTCHA**: Cloudflare Turnstile, reCAPTCHA — bez řešení (2Captcha stojí $3/1000) se nedostaneš dál.

## 8.3 Architektonická rizika

- **Přílišná inspirace obscurou**: Samuel Seidel je individual, ty jsi taky individual — ale patterny z obscura jsou **overkill** pro malý MCP server. Začni jednoduše (jeden Node.js process, jeden MCP server, jeden tool), iteruj.
- **Předčasná abstrakce**: Workspace monorepo s 5 balíčky je zbytečné, pokud máš 2 nástroje. Počkej, až budeš mít 5+ nástrojů.
- **Cargo cult programming**: `cargo --features stealth`, `LocalSet`, `multi-worker serve` jsou **kontextově specifická řešení**. Slepě je kopírovat = anti-pattern.

---

# 9. Reference a další čtení

## 9.1 Zdrojové soubory obscura (zkopírované v `/workspace/obscura-analysis/src/`)

*Poznámka: Analyzovaný kód pochází z upstreamu `h4ckf0r0day/obscura` (jediný zdroj, který obsahuje relevantní kód). Samuelův fork obsahuje stejný kód mínus crates `obscura-mcp` a `obscura`.*

- `Cargo_root.toml` — workspace manifest
- `crates_obscura-cdp_src_server.rs` (27KB) — CDP server, request interception, network events
- `crates_obscura-cli_src_main.rs` (26KB) — CLI subcommands, multi-worker serve, parallel scrape
- `crates_obscura-browser_src_page.rs` (32KB) — Page lifecycle, navigation, scripts execution
- `crates_obscura-browser_src_context.rs` — BrowserContext, Arc pattern
- `crates_obscura-browser_src_lifecycle.rs` — LifecycleState + WaitUntil enum
- `crates_obscura-net_src_client.rs` — HTTP client, validate_url (SSRF prevence)
- `crates_obscura-net_src_cookies.rs` (312 řádků) — CookieJar
- `crates_obscura-net_src_robots.rs` — RobotsCache, robots.txt parser
- `crates_obscura-net_src_interceptor.rs` — RequestInterceptor trait
- `crates_obscura-dom_src_tree.rs` (548 řádků) — DomTree, NodeId, attributes
- `crates_obscura-dom_src_selector.rs` (542 řádků) — CSS selector engine
- `crates_obscura-cdp_src_types.rs` — CdpRequest/Response/Event
- `.github_workflows_release.yml` — Multi-platform release

## 9.2 Další repozitáře Samuela Seidela (konzultované pro kontext jeho přístupu)

*Poznámka: Tyto repozitáře jsou Samuelovy vlastní projekty (ne forky) a poskytují kontext o jeho přístupu k AI-assisted vývoji. Nejsou součástí obscura ekosystému.*

- `samuelseidel/landomo-canada-realtor` (TypeScript, 4.2.2026) — Phase 2 architektura: Coordinator + Workers + Verifier, Redis queue, PostgreSQL snapshots, Prometheus metrics, adaptive scheduling
- `samuelseidel/eu-ai-act-legal-rag` (HTML, 15.7.2026) — 1389-uzlový provision graph, citation verification, abstention gates
- `samuelseidel/cybertruck-experience` (Next.js 16.2.9) — Demo Next.js 16 + React 19 + framer-motion 12 + Tailwind 4
- `samuelseidel/ciphermesh` (TypeScript) — P2P messaging s Kademlia DHT

## 9.3 Kognitivní artefakt (vstupní)

- `/workspace/attachments/75e988a2__2b187fef-df21-4ea5-ab12-bbf0b00f4678.md` — *Kognitivní transfer v reverse engineeringu* (Gick & Holyoak, Holyoak & Thagard, Gentner, Chase & Simon, Klein, Polanyi, Luchins, Koriat)

## 9.4 Knihovny a nástroje k evaluaci

**Pro Python MCP/Scraping stack:**
- `mcp` (Anthropic official Python SDK): https://github.com/modelcontextprotocol/python-sdk
- `playwright` + `playwright-stealth` — browser automation
- `httpx` + `httpx-retries` + `httpx-sse` — async HTTP
- `curl_cffi` — TLS fingerprint impersonation
- `cookie_store` — RFC 6265 cookies
- `reppy` nebo `urllib.robotparser` — robots.txt
- `tldextract` — public suffix list
- `sqlalchemy[asyncio]` + `asyncpg` — async PostgreSQL
- `arq` nebo `rq` — Redis job queue
- `prometheus-client` — metrics
- `structlog` — structured logging
- `uv` — Python package management (workspace support)
- `cibuildwheel` — cross-platform wheel builds

**Pro TypeScript MCP/Scraping stack:**
- `@modelcontextprotocol/sdk` — Anthropic official TS SDK
- `playwright` + `playwright-extra` + `puppeteer-extra-plugin-stealth`
- `axios` + `axios-retry`
- `tough-cookie` — RFC 6265 cookies
- `robots-parser` — robots.txt
- `ioredis` + `bullmq` — Redis job queue
- `pg` — PostgreSQL
- `prom-client` — metrics
- `pnpm` — monorepo workspace
- `tsup` — bundling

---

# 10. Závěr — proč tahle analýza dává smysl (i přes chybnou atribuci)

Tvůj pocit *„obscura by mohla být inspirace pro outpost2026"* je korektní instinkt (kognitivní artefakt, sekce 2.4 — feeling of knowing z Koriat 2007). Důvody:

1. **Strukturální podobnost** (Gentner 1983): oba projekty řeší *orchestraci izolovaných worker procesů s JSON-RPC protokolem, context-based state management, request interception, a graceful degradation*. Povrch (Rust vs Python/TS, V8 vs CPython, headless browser vs MCP server) je odlišný — relační struktura je identická.

2. **Cílová podobnost** (Holyoak & Thagard 1995): oba projekty cílí na *umožnit AI agentům interagovat s webem bezpečně, škálovatelně, s právní compliance*. obscura pro scraping realit, outpost2026 pro scraping pracovních portálů + LinkedIn.

3. **Expertní pattern matching** (Chase & Simon 1973): tvůj cognitivní systém — po iteracích na vlastním MCP server stacku — rozpoznal, že obscura implementuje *stejný abstraktní workflow* (process isolation, JSON-RPC, dispatcher, request capture, robots compliance), který ty sám instinktivně buduješ.

4. **Tacitní znalost externalizovaná přes LLM** (Polanyi 1966 + kognitivní artefakt sekce 5.2): tento dokument je výsledkem 4-fázového procesu, ve kterém LLM (já) extrahuje explicitní patterny z kódu obscura a mapuje je na tvou explicitní doménu.

**Důležitá nuance**: Architektonické patterny pochází od **h4ckf0r0day teamu** (302 commitů, 19.3k ⭐, 8+ contributorů), ne od Samuela Seidela. Samuel obscura forknul a přidal 1 commit pro svůj use case. To nesnižuje hodnotu patternů — naopak, ukazuje, že jsou osvědčené v produkčním open-source projektu se skutečnou komunitou.

**Co sledovat dále:**
- **Primárně**: `h4ckf0r0day/obscura` — upstream s aktivním vývojem, MCP serverem, novými features
- **Sekundárně**: `samuelseidel/landomo-canada-realtor` — Samuelův vlastní projekt s Phase 2 architekturou (relevantní pro tvůj plánovaný multi-portál scraper)

**Akce**: Použij tento dokument jako vstup pro Fázi 1 (Příprava) roadmapy v sekci 6.1. Pokud máš dotazy k jakémukoli patternu nebo potřebuješ konkrétní implementaci některého z 12 patternů v sekci 4, jsem ready.

---

# Appendix A: Kompletní seznam zkopírovaných souborů obscura (z upstreamu h4ckf0r0day/obscura)

| **Cesta v repu** | **Velikost** | **Význam** |
|---|---|---|
| `Cargo.toml` | 1196 B | Workspace manifest |
| `crates/obscura-browser/Cargo.toml` | 464 B | Browser crate manifest |
| `crates/obscura-cdp/Cargo.toml` | 543 B | CDP crate manifest |
| `crates/obscura-cli/Cargo.toml` | 714 B | CLI crate manifest |
| `crates/obscura-dom/Cargo.toml` | 373 B | DOM crate manifest |
| `crates/obscura-js/Cargo.toml` | 554 B | JS runtime crate manifest |
| `crates/obscura-net/Cargo.toml` | 528 B | Net crate manifest |
| `crates/obscura-browser/src/lib.rs` | 165 B | |
| `crates/obscura-browser/src/context.rs` | 3 801 B | BrowserContext (Arc state) |
| `crates/obscura-browser/src/lifecycle.rs` | 971 B | LifecycleState + WaitUntil |
| `crates/obscura-browser/src/page.rs` | 32 191 B | Page navigation, network events |
| `crates/obscura-cdp/src/lib.rs` | 137 B | |
| `crates/obscura-cdp/src/server.rs` | 27 592 B | CDP server, request interception |
| `crates/obscura-cdp/src/dispatch.rs` | 7 172 B | CDP method dispatch table |
| `crates/obscura-cdp/src/types.rs` | 1 898 B | CdpRequest/Response/Event |
| `crates/obscura-cli/src/main.rs` | 26 303 B | CLI: serve/fetch/scrape subcommands |
| `crates/obscura-cli/src/worker.rs` | 4 520 B | Worker process JSON-RPC protocol |
| `crates/obscura-dom/src/lib.rs` | 218 B | |
| `crates/obscura-dom/src/tree.rs` | 21 740 B | DomTree, NodeId, attributes |
| `crates/obscura-dom/src/selector.rs` | 19 448 B | CSS selector engine (Servo) |
| `crates/obscura-net/src/lib.rs` | 444 B | |
| `crates/obscura-net/src/client.rs` | 16 701 B | HTTP client, validate_url (SSRF) |
| `crates/obscura-net/src/cookies.rs` | 17 601 B | CookieJar, domain matching |
| `crates/obscura-net/src/interceptor.rs` | 333 B | RequestInterceptor trait |
| `crates/obscura-net/src/robots.rs` | 4 950 B | RobotsCache, robots.txt parser |
| `crates/obscura-net/src/blocklist.rs` | 1 738 B | pgl_domains.txt (58KB tracker list) |
| `crates/obscura-js/src/lib.rs` | 91 B | |
| `crates/obscura-js/src/runtime.rs` | 59 614 B | V8 runtime (deno_core) wrapper |
| `crates/obscura-js/src/ops.rs` | 24 570 B | Rust op bindings pro DOM API |
| `crates/obscura-js/src/module_loader.rs` | 2 726 B | Module loader |
| `crates/obscura-js/build.rs` | 1 316 B | V8 snapshot path env var |
| `.github/workflows/release.yml` | 1 846 B | Multi-platform release (4 OS × 2 features) |
| `.cargo/config.toml` | 30 B | |

**Celkem zkopírováno**: ~280 KB Rust kódu, 25 souborů, 6 Cargo manifestů.

---

**Konec dokumentu. Verze 1.0 — 2026-07-17. Pro feedback nebo rozšíření viz `/workspace/obscura-analysis/`.**
