# Orchestrator CLI

> **Cost-aware, token-efficient LLM orchestration with semantic caching** — one command, every model you already pay for, zero wasted tokens, and a cache that actually understands natural language.

Connect your provider accounts (**Anthropic**, **OpenAI**, **Groq**, **Google Gemini**). The system normalises every model across all your connected accounts into one registry and routes each prompt to the cheapest model that satisfies the task — with a semantic cache that recognises when two differently-worded prompts ask the same thing.

An optional **agent mode** runs a multi-step tool loop (read/write files, search, run Python/pytest, optional shell) under a configurable sandbox, still routing each LLM step across all connected tool-capable models.

---

## Table of Contents

1. [Why this exists](#why-this-exists)
2. [Features](#features)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [First-time setup](#first-time-setup)
6. [Connecting providers](#connecting-providers)
7. [Immersive TUI shell](#immersive-tui-shell)
8. [CLI commands reference](#cli-commands-reference)
9. [Semantic cache](#semantic-cache)
10. [Agent mode](#agent-mode)
11. [Configuration](#configuration)
12. [Architecture](#architecture)
13. [Tech stack](#tech-stack)
14. [Running tests](#running-tests)
15. [Roadmap](#roadmap)

---

## Why this exists

If you have API keys for multiple LLM providers, you're probably:

- Manually choosing which model to call for each task
- Paying for the same answer twice when you rephrase a prompt
- Losing track of what everything costs

Orchestrator solves all three. You describe your task; the system picks the cheapest model that can handle it, checks a semantic cache first (so rephrased duplicates cost $0.00), and logs every call with token counts and USD cost.

**Why semantic cache instead of exact cache?**  
"Summarize this doc" and "Give me a summary of this doc" are two different hash keys — exact cache misses every time. Both embed to nearly identical vectors, so semantic cache gives a single hit. For an LLM router this is the right default: users rephrase constantly.

---

## Features

| Feature | Detail |
|---------|--------|
| **Semantic cache** | Local `all-MiniLM-L6-v2` embeddings, Qdrant ANN search. Hit threshold: cosine ≥ 0.92. No API call needed for lookups. |
| **Multi-provider routing** | Anthropic, OpenAI, Groq, Gemini — all models in one registry, sorted cheapest-first per task. |
| **Dynamic model discovery** | On `connect`, the provider's `/models` API is called to discover *all* models your key has access to (not just a hardcoded 3). Dated aliases resolved by prefix matching. |
| **Task classification** | Auto-detects `simple`, `json_extract`, `reasoning`, `vision`, `tools` from the prompt. |
| **Cost tracking** | Every request traced: token counts, USD cost, latency, cache hit/miss, similarity score. |
| **Agent tools** | ReAct loop with sandboxed file I/O, codebase search, Python/pytest, optional shell. |
| **Encrypted credentials** | API keys Fernet-encrypted before SQLite write. |
| **Immersive TUI** | Full-screen Textual shell — runs on `orchestrator` (no args, interactive TTY). |
| **Zero-config vector store** | Qdrant embedded in-process. No Docker, no daemon. |

---

## Prerequisites

- **Python 3.11+**
- A terminal that supports 256-colour ANSI (Windows Terminal, iTerm2, most modern terminals)
- API keys for at least one of: OpenAI, Anthropic, Groq, Google Gemini

---

## Installation

```bash
git clone https://github.com/Executioner-Cs/Cost_Aware_LLM_Proj.git
cd Cost_Aware_LLM_Proj

# Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Install with all dev dependencies
pip install -e ".[dev]"
```

> **Always activate `.venv` before running `pip install`** so packages stay in the project environment, not your system Python.

---

## First-time setup

```bash
orchestrator init
```

What it does:

1. Creates `~/.orchestrator/` with:
   - `config.toml` — default routing, cache, agent settings
   - `orchestrator.db` — SQLite database (accounts, models, traces, cache, tool calls)
   - `qdrant/` — embedded Qdrant vector store
2. Downloads and caches the embedding model (`all-MiniLM-L6-v2`, ~22 MB) on first run.
3. On an interactive terminal, shows an **arrow-key provider picker** — connect your first account without leaving the init flow.
4. After connecting (or skipping), **automatically launches the immersive TUI shell** so you can start using the tool immediately.

If you're running in a non-interactive environment (CI, piped input), `init` prints the manual next steps instead.

---

## Connecting providers

### Option 1 — Environment variables / `.env` file (recommended for local dev)

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

```text
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
```

Keys are picked up automatically by `orchestrator connect` and by the init provider picker.

### Option 2 — CLI prompt

```bash
orchestrator connect openai      # prompts for key
orchestrator connect anthropic
orchestrator connect groq
orchestrator connect gemini
```

On Windows Terminal, paste into the key prompt with `Ctrl+Shift+V` (characters don't echo — that's normal).

### Option 3 — Inline in TUI

Inside the TUI shell, pass the key directly:

```
orchestrator > connect openai sk-proj-...
```

### What connect does

- Validates the API key against the provider
- Calls `/models` to discover **all** models your key has access to (not a hardcoded list)
- Stores the encrypted key and model registry in SQLite
- Only connected providers participate in routing

---

## Immersive TUI shell

Run with no arguments on an interactive terminal:

```bash
orchestrator          # launches full-screen TUI
orchestrator shell    # explicit alias — same result
```

The TUI opens a full-screen Textual application. Your terminal prompt disappears; all commands run inside the orchestrator environment.

### Layout

```
┌── ORCHESTRATOR ─────────────── providers: 2  cache ON  quality: balanced ──┐
│                                                              │ Recent        │
│  Main output panel (scrollable)                             │ Activity      │
│                                                              │               │
├──────────────────────────────────────────────────────────────┴───────────────┤
│  orchestrator > ___________________________________________________________  │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Status bar** — live provider count, cache on/off, quality mode, session cost
- **Main output panel** — command results, Rich tables, agent output
- **Side panel** — recent route activity
- **Input bar** — type commands without the `orchestrator` prefix

### Key bindings

| Key | Action |
|-----|--------|
| `Enter` | Run command |
| `↑` / `↓` | Navigate command history |
| `Escape` | Clear input |
| `Ctrl+C` | Clear input (TUI stays open) |
| `Ctrl+L` | Clear the output panel |
| `Ctrl+Q` | Quit the TUI |

### Commands inside the TUI

```
orchestrator > help
orchestrator > connect openai sk-proj-...
orchestrator > accounts list
orchestrator > model list
orchestrator > route "Summarize this meeting note"
orchestrator > route "Extract line items as JSON" --task json_extract
orchestrator > route "Reason through this" --quality best
orchestrator > cache stats
orchestrator > trace list
orchestrator > agent run "Fix the failing tests"
orchestrator > quality best
orchestrator > clear
orchestrator > exit
```

### Accounts list — interactive widget

`accounts list` opens an interactive panel instead of a plain table:

```
┌── Connected Accounts (2 total)  ↑↓ Navigate  D Kill Account  V View ID  Esc Close ──┐
│  ID              Provider  Name              Connected At         Status              │
│ ▶ f1900a7b-2841…  openai   MAYANK KHANDELWAL  2026-04-09 12:22:39  active             │
│   3dacfed8-...…   anthropic  Anthropic account  2026-04-09 13:00:00  active           │
│                                                                                       │
│  [Kill Account]  [View ID]                                                            │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

| Action | How |
|--------|-----|
| **Kill Account** | Select row → click `[Kill Account]` or press `D`. Removes the account and all its models from the registry. |
| **View ID** | Select row → click `[View ID]` or press `V`. Shows the full UUID in a notification. |
| **Close** | Press `Esc` |

To disconnect from the plain CLI (outside TUI):

```bash
# Partial IDs work — no need to type the full UUID
orchestrator accounts disconnect f1900a7b
```

---

## CLI commands reference

### `orchestrator init`

Set up home directory, database, vector store, and download the embedding model. Safe to re-run — skips steps that are already complete.

### `orchestrator connect <provider>`

```bash
orchestrator connect openai
orchestrator connect anthropic
orchestrator connect groq
orchestrator connect gemini
```

Validates the key and discovers **all** models available to it via the provider's API. Stores encrypted credentials in SQLite.

### `orchestrator accounts list|sync|disconnect`

```bash
orchestrator accounts list
orchestrator accounts sync <account-id>       # re-validate key + refresh models
orchestrator accounts disconnect <account-id> # partial ID prefix works
```

### `orchestrator model list`

Shows every model in the registry with pricing and capability flags. Dynamic discovery means you see the full model catalogue your key has access to:

```
Provider    Model              Tier      Ctx      $/1M in   $/1M out  JSON  Tools  Vision
openai      gpt-4.1-nano       small     1000k    $0.10     $0.40     ✓     ✓      ✓
openai      gpt-4o-mini        small     128k     $0.15     $0.60     ✓     ✓      ✓
openai      gpt-4.1-mini       small     1000k    $0.40     $1.60     ✓     ✓      ✓
openai      gpt-4o             balanced  128k     $2.50     $10.00    ✓     ✓      ✓
openai      gpt-4.1            balanced  1000k    $2.00     $8.00     ✓     ✓      ✓
openai      o3-mini            balanced  200k     $1.10     $4.40     ✓     ✓      ✗
openai      o1                 large     200k     $15.00    $60.00    ✓     ✓      ✓
openai      gpt-5              large     1000k    $25.00    $75.00    ✓     ✓      ✓
```

### `orchestrator route <prompt> [flags]`

```bash
orchestrator route "Summarize this meeting note"
orchestrator route "Extract line items as JSON: ..." --task json_extract
orchestrator route "Reason through this tradeoff" --quality best
orchestrator route "What would this cost?" --dry-run
```

| Flag | Values | Default |
|------|--------|---------|
| `--task` | `simple`, `json_extract`, `reasoning`, `vision`, `tools` | auto-detected |
| `--quality` | `cheap`, `balanced`, `best` | `balanced` |
| `--dry-run` | — | off |

**Cache miss output:**
```
Task       simple
Route      simple_task_cheapest_model
Provider   openai
Model      gpt-4o-mini
Cache      miss
Tokens     48 in / 112 out
Cost       $0.000083
Latency    0.9s

╭─ Answer ──────────────────╮
│ [response]                │
╰───────────────────────────╯
```

**Cache hit output (free):**
```
Task       simple
Route      semantic_cache_hit
Cache      HIT  (similarity: 0.961)
Cost       $0.000000
Latency    0.012s

╭─ Answer ──────────────────╮
│ [cached response]         │
╰───────────────────────────╯
```

### `orchestrator trace list|show`

```bash
orchestrator trace list
orchestrator trace list --limit 50
orchestrator trace show <trace-id>
```

Every trace records: prompt preview, task type, provider, model, cache hit/miss, similarity score, token counts, cost, latency, status.

### `orchestrator cache stats|inspect|clear|threshold`

```bash
orchestrator cache stats                          # overview + top reused entries
orchestrator cache inspect <entry-id>             # full detail on one entry
orchestrator cache clear                          # clear all
orchestrator cache clear --task-type json_extract # clear by task type
orchestrator cache threshold 0.95                 # tighten similarity threshold
```

### `orchestrator agent <subcommand>`

```bash
orchestrator agent run "Implement feature X in src/foo.py" --quality best
orchestrator agent edit path/to/file.py "Add type annotations"
orchestrator agent explain path/to/file.py
orchestrator agent fix-tests
orchestrator agent refactor src/ "Extract shared helper"
```

Common flags on `run`:

| Flag | Description |
|------|-------------|
| `--quality` | `cheap` / `balanced` / `best` |
| `--max-iterations` | Max agent loop turns (default: 8) |
| `--plan` | Generate a plan before executing |
| `--plan-llm` | Model to use for planning |

The agent uses sandboxed file I/O, Python execution, and pytest. Shell is **off by default** — enable with `allow_shell = true` in `config.toml`.

---

## Semantic cache

### How it works

```
Prompt → embed locally (~5ms, no API call)
       → Qdrant ANN search  (filter: task_type + quality must match exactly)
       → score ≥ 0.92 → HIT  → fetch response from SQLite → return (cost: $0.00)
       → score < 0.92 → MISS → call provider → store result → return
```

### Cache key

`(embedding vector, task_type, quality)` — similarity alone is not enough. A `json_extract` result is never served to a `reasoning` query.

### Thresholds

| Range | Meaning |
|-------|---------|
| ≥ 0.98 | Near-exact wording only |
| 0.92–0.97 | Same question, different phrasing ✓ (default zone) |
| 0.85–0.91 | Related but not the same — too loose |
| < 0.85 | Different topic |

Per-task-type thresholds can be tightened in `config.toml` (e.g. `task_thresholds.json_extract = 0.95`).

### Qdrant + SQLite split

Qdrant stores vectors and lightweight metadata (task_type, quality, sqlite_id). SQLite stores full response text, token counts, and cost metadata. They are linked by a shared UUID. This keeps Qdrant fast and lean for ANN search.

---

## Agent mode

The agent runs a **ReAct-style loop**: plan → act (call tool) → observe → repeat.

- **Model selection per turn**: lists all enabled models with `supports_tools`, picks cheapest that fits context + quality. Works across all connected providers simultaneously.
- **Semantic cache**: NOT used for agent turns (message history is unique per run).
- **Sandbox**: all file I/O is confined under `sandbox_root`. Shell disabled by default.
- **Tool definitions**: single source in `schemas/tools.py`. OpenAI/Groq use native function calling; Anthropic adapter maps the same shapes to the Messages API.

### Macro DSL (token-saving goal prefix)

Prefix the agent goal with a compact inline macro block. Macros expand into system-prompt constraints locally — no model tokens spent on boilerplate.

```
{BRPR,VENV,NOFAKE} Implement feature X
{CX:2K,TOOLSUM:1K} Fix failing tests with minimal context
```

See `skills/macro-hand-sign-dsl/SKILL.md` for the full macro table.

---

## Configuration

Located at `~/.orchestrator/config.toml` (created by `orchestrator init`):

```toml
[routing]
default_quality = "balanced"   # cheap | balanced | best
prefer_cheapest = true
fallback_enabled = true

[cache]
enabled = true
ttl_seconds = 86400            # 24h default TTL
similarity_threshold = 0.92    # global cosine similarity threshold
task_thresholds.json_extract = 0.95   # stricter for structured extraction
task_thresholds.reasoning = 0.93
embedding_model = "all-MiniLM-L6-v2"

[cost]
warn_above_usd = 0.01
monthly_budget_usd = 0         # 0 = no limit

[display]
show_cost = true
show_tokens = true
show_route_reason = true
show_cache_similarity = true

[agent]
sandbox_root = "."             # paths resolved relative to cwd
max_iterations = 8
max_file_bytes = 1048576       # 1 MB max file read
max_subprocess_seconds = 120
allow_shell = false            # enable only in trusted environments
blocked_shell_patterns = "rm -rf,mkfs,dd if=,:(){:|:&};:"
network_disabled = true        # documented intent; not full OS network isolation
```

---

## Architecture

### Repository layout

```
orchestrator_cli/
├── cli/
│   ├── main.py                  ← Typer app, hybrid TUI/CLI entrypoint
│   ├── commands/                ← connect, accounts, model, route, trace, cache, agent, shell
│   └── tui/
│       ├── app.py               ← Textual App (SessionState, StatusBar, layout)
│       ├── dispatcher.py        ← Parses TUI commands → service calls → Rich renderables
│       ├── widgets.py           ← Interactive widgets (AccountsWidget with Kill/View buttons)
│       └── style.tcss           ← Textual CSS layout
├── agent/
│   ├── loop.py                  ← ReAct-style agent loop
│   ├── dispatcher.py            ← tool name → sandboxed execution
│   ├── sandbox.py               ← path confinement
│   ├── planner.py               ← optional planning preamble
│   ├── tool_logging.py          ← SQLite tool_calls rows
│   └── tools/                   ← file_io, search, execution
├── core/
│   ├── router.py                ← 10-step routing pipeline
│   ├── llm_turn.py              ← agent chat turn (no cache; multi-provider)
│   ├── classifier.py            ← task type detection
│   ├── model_selector.py        ← cost-ranked selection (pure logic)
│   ├── cost_estimator.py        ← token × price math
│   ├── semantic_cache.py        ← Qdrant + SQLite cache layer
│   └── reasons.py               ← route reason code constants
├── providers/
│   ├── base.py                  ← BaseConnector, BaseAdapter ABCs
│   ├── anthropic/               ← Messages API + tool calling, dynamic discovery
│   ├── openai/                  ← Chat Completions + tools, dynamic discovery
│   ├── groq/                    ← OpenAI-compatible endpoint
│   └── gemini/                  ← Google GenAI text + chat_with_tools
├── services/
│   ├── init_service.py          ← orchestrator init logic + post-init TUI handoff
│   ├── connect_service.py
│   ├── account_service.py       ← list, sync, disconnect (prefix-based ID lookup)
│   ├── model_service.py
│   ├── routing_service.py
│   └── trace_service.py
├── db/
│   ├── models.py                ← ORM: accounts, model_registry, traces, cache_entries, tool_calls
│   ├── session.py
│   └── repositories/            ← per-table CRUD
├── embeddings/
│   ├── embedder.py              ← sentence-transformers singleton
│   └── model_cache.py
├── schemas/
│   ├── routing.py               ← RouteRequest, RouteResult
│   └── tools.py                 ← AGENT_TOOLS_OPENAI (provider-neutral)
└── utils/
    ├── crypto.py                ← Fernet encryption/decryption
    ├── console.py               ← Rich console singleton
    ├── env.py                   ← dotenv loader, provider key lookup
    ├── setup_interactive.py     ← questionary provider picker
    └── setup_ui.py              ← init banner and panel renderers
```

### Routing pipeline (10 steps)

```
1.  Normalise prompt          strip + collapse whitespace
2.  Classify task             keyword + heuristic rules
3.  Embed prompt              local sentence-transformers, ~5ms, 384-dim
4.  Cache lookup              Qdrant ANN + payload filter → HIT returns immediately
5.  Estimate token count      provider-specific tokenisation estimate
6.  Select model              cheapest model satisfying tier + capability constraints
7.  Call provider             adapter.generate(prompt, model_id, key)
8.  Validate output           empty check; JSON parse for json_extract
9.  Store in cache            Qdrant upsert + SQLite INSERT
10. Write trace               tokens, cost, latency, route_reason → return
```

---

## Tech stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.11+ | Typer, async, ecosystem |
| CLI | Typer | Type-safe, fast |
| Schema validation | Pydantic v2 | Uniform request/response |
| ORM | SQLAlchemy 2.x | Session-based |
| Database | SQLite | Single-file, zero-config |
| Vector store | Qdrant (embedded) | In-process, no server |
| Embedding model | `all-MiniLM-L6-v2` | 384-dim, local, ~5ms |
| Config | TOML | Human-readable |
| Credential storage | `cryptography` (Fernet) | AES encryption |
| Console output | `rich` | Tables, panels, colour |
| Immersive TUI | `textual` | Full-screen terminal app |
| Interactive setup | `questionary` | Arrow-key provider picker |
| HTTP client | `httpx` | All provider adapters |
| Testing | `pytest` + `pytest-asyncio` | Standard |

---

## Running tests

```bash
# Activate venv first
pip install -e ".[dev]"
pytest
```

Test coverage includes:
- Task classifier — parameterised cases for all task types
- Cost estimator — token estimation and USD math
- Model selector — tier/capability/context window constraints
- Semantic cache — hit/miss, hard filters, hit count, clear
- Router integration — mocked provider, dry-run, no-models error
- Provider adapters — Groq, Gemini
- CLI connect flows — env var / dotenv / inline key precedence
- E2E CLI simulation — help, error handling, output styles

---

## Roadmap

- [x] Multi-provider routing (Anthropic, OpenAI, Groq, Gemini)
- [x] Semantic cache (Qdrant + sentence-transformers, local)
- [x] Cost tracking and trace history
- [x] Agent / tool-use routing (`orchestrator agent`)
- [x] Gemini `chat_with_tools` support
- [x] Immersive TUI shell (`orchestrator` / `orchestrator shell`)
- [x] Dynamic model discovery — all models your key has access to
- [x] Interactive accounts widget with Kill Account + View ID buttons
- [x] Provider picker on init + auto-launch TUI after setup
- [x] Prefix-based account ID lookup (`accounts disconnect f1900a7b`)
- [ ] OAuth 2.0 (V2 — currently API key / PAT only)
- [ ] Hard budget enforcement (warn-only in V1)
- [ ] FastAPI wrapper
- [ ] Postgres support
