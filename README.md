# Orchestrator CLI

> A local CLI tool for **cost-aware, token-efficient LLM orchestration with semantic caching**.

Connect your existing provider accounts (**Anthropic**, **OpenAI**, **Groq**, **Google Gemini**), and the system routes every prompt to the cheapest model that can satisfy the task — with a semantic cache layer that recognises when two differently-worded prompts are asking the same thing. An optional **agent** mode runs a tool loop (read/write/search/run/tests) under a configurable sandbox, still routing each LLM step across **all** connected tool-capable models.

**The core value proposition**: one command, every model you already pay for, zero wasted tokens, and a cache that actually works in natural language.

---

## Features

- **Semantic cache** — "Summarize this doc" and "Give me a summary of this doc" both hit the same cache entry. Powered by `all-MiniLM-L6-v2` running entirely locally (no API call needed for lookups).
- **Multi-provider routing** — Anthropic, OpenAI, Groq, and Gemini models normalised into one registry. Cheapest model that satisfies constraints wins. Connect as many accounts as you like; all enabled models compete for each request (and for each agent step).
- **Agent tools** — `orchestrator agent` runs a ReAct-style loop with sandboxed file I/O, codebase search, Python execution, optional shell (off by default), and pytest. Tool definitions are provider-neutral; OpenAI/Groq use native function calling, Anthropic’s API is adapted internally. **Semantic cache is not used for agent LLM steps** (non-deterministic transcripts).
- **Task classification** — Automatically detects `simple`, `json_extract`, `reasoning`, `vision`, and `tools` task types from the prompt.
- **Cost tracking** — Every request is traced with token counts, USD cost, latency, and cache similarity score.
- **Zero-config vector store** — Qdrant runs embedded (in-process), no Docker or server required.
- **Encrypted credentials** — API keys are Fernet-encrypted before writing to SQLite.

---

## Quickstart

### 1. Install

Create and **activate** a virtual environment first (so dependencies land in the project venv, not the system Python). Then install the package in editable mode with dev extras.

```bash
git clone https://github.com/Executioner-Cs/Cost_Aware_LLM_Proj.git
cd Cost_Aware_LLM_Proj
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
```

Always activate `.venv` before running `pip install` or `pip` upgrades in this repo.

### 2. Initialise

```bash
orchestrator init
```

Creates `~/.orchestrator/` with `config.toml`, `orchestrator.db`, and the Qdrant vector store. Also downloads and caches the embedding model on first run.

At the end of `init`, interactive terminals now show a staged handoff prompt and an arrow-key provider picker (`openai`, `anthropic`, `gemini`, `groq`), then immediately start the selected `connect` flow.

If interactivity is unavailable, `init` explains why and falls back cleanly:
- non-TTY sessions: prints manual next-step commands
- missing picker dependency: prints install hint (`pip install -e ".[dev]"` in active `.venv`)
- cancelled picker/key entry: prints manual connect commands

### 3. Connect a provider

```bash
orchestrator connect anthropic   # uses .env/env var if present; otherwise prompts
orchestrator connect openai
orchestrator connect groq
orchestrator connect gemini
```

You can also pre-seed keys via a repo-root `.env` file (recommended for local dev):

```bash
cp .env.example .env
```

Then set keys like:

```text
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
```

Pasting into a hidden prompt: your paste will work even though characters don’t show. In Windows Terminal, use `Ctrl+Shift+V` (or right-click paste).

Each successful connect validates the key and registers that provider’s models. Only **connected** providers participate in routing.

### 4. Route a prompt

```bash
orchestrator route "Summarize this meeting note"
orchestrator route "Extract line items as JSON: ..." --task json_extract
orchestrator route "Reason through this architectural tradeoff" --quality best
orchestrator route "What would this cost?" --dry-run
```

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

╭─ Answer ─────────────────────────────╮
│ [response text]                      │
╰──────────────────────────────────────╯
```

**Cache hit output:**
```
Task       simple
Route      semantic_cache_hit
Cache      HIT  (similarity: 0.961)
Cost       $0.000000
Latency    0.012s

╭─ Answer ─────────────────────────────╮
│ [cached response]                    │
╰──────────────────────────────────────╯
```

---

## CLI Reference

### `orchestrator init`
Set up the home directory, SQLite database, Qdrant collection, and warm up the embedding model. After setup completes, interactive terminals get a compact Claude-like handoff, provider picker, and immediate connect flow (with hidden API-key prompt fallback). Non-interactive or unsupported sessions fall back to manual `orchestrator connect <provider>` commands with troubleshooting hints.

### `orchestrator connect <provider>`
Connect a provider using an API key (PAT). Validates the key and populates the model registry. Providers: `anthropic`, `openai`, `groq`, `gemini`.

### `orchestrator accounts list|sync|disconnect`
Manage connected accounts. `sync` re-validates the key and refreshes the model list.

### `orchestrator model list`
List all models in the registry with tier, pricing, and capability flags.

```
Provider    Model                  Tier      Ctx     $/1M in   $/1M out
anthropic   claude-haiku-4-5       small     200k    $0.25     $1.25
anthropic   claude-sonnet-4-6      balanced  200k    $3.00     $15.00
openai      gpt-4o-mini            small     128k    $0.15     $0.60
openai      gpt-4o                 balanced  128k    $2.50     $10.00
```

### `orchestrator` (default immersive mode)

When you run `orchestrator` with **no subcommand** in an **interactive terminal**, it launches the immersive TUI — a full-screen terminal interface powered by [Textual](https://textual.textualize.io/). The PowerShell/bash prompt disappears; all commands run within the orchestrator environment until you explicitly exit.

```bash
orchestrator          # interactive TTY → immersive TUI
orchestrator shell    # explicit alias — same result
```

Non-interactive environments (piped input, CI) get the standard help text instead.

On startup, the TUI bootstraps session state: loads config, checks DB/Qdrant readiness, and collects connected provider and model summaries. The header subtitle shows a live status line (provider count, model count, cache on/off, quality mode).

**Inside the shell**, type any command without the `orchestrator` prefix:

```
orchestrator > help                          # list all commands
orchestrator > connect openai sk-proj-...    # connect with an API key
orchestrator > model list                    # browse the model registry
orchestrator > route "Summarize this doc"    # route a prompt
orchestrator > cache stats                   # check cache analytics
orchestrator > agent run "Fix tests"         # run the agent loop
orchestrator > exit                          # return to terminal
```

**Shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Execute command |
| `Escape` | Clear input |
| `Ctrl+C` | Clear input (app stays alive) |
| `Ctrl+Q` | Quit the shell |

The header updates after state-mutating commands (`connect`, `init`, `accounts`). The connect flow inside the shell uses the same precedence (explicit key > .env/env var) but prompts are replaced by inline arguments — type `connect <provider> <key>` directly.

### `orchestrator agent …`

Sandboxed tool-using agent. Each **turn** picks the cheapest **tool-capable** model among OpenAI, Anthropic, Groq, and Gemini (all use the same unified tool schema; adapters translate to each API).

| Command | Description |
|--------|-------------|
| `agent run "<goal>"` | Full loop: `--quality`, `--max-iterations`, `--plan`, `--plan-llm` |
| `agent edit <file> "<instruction>"` | Shorthand goal to read/modify one file |
| `agent explain <file>` | Read and explain a file |
| `agent fix-tests` | Run tests and iterate on fixes |
| `agent refactor <target> "<instruction>"` | Refactor with planning preamble |

Configure limits and sandbox root under `[agent]` in `config.toml` (see below). **Shell commands are disabled by default** (`allow_shell = false`). Set `allow_shell = true` only in trusted environments.

### Macros (token-saving goal prefix)

For repeated workflows, you can prefix the agent goal with a compact inline macro block. This block is expanded **locally** into additional system-prompt constraints (no model tokens spent) and removed from the actual goal.

Examples:

```text
{BRPR,VENV,NOFAKE,DOCSYNC} Implement feature X
{CX:2K,TOOLSUM:1K,NOFAKE} Fix failing tests with minimal context
```

See `skills/macro-hand-sign-dsl/SKILL.md` for the full macro table and guidance.

### `orchestrator route <prompt> [flags]`

| Flag | Description |
|---|---|
| `--task` | Override auto-detected task type (`simple`, `json_extract`, `reasoning`, `vision`, `tools`) |
| `--quality` | `cheap` / `balanced` (default) / `best` |
| `--dry-run` | Show routing plan and estimated cost without calling the provider |

### `orchestrator trace list|show`
Browse routing history. Every trace includes cache hit status, similarity score, token counts, cost, and latency.

### `orchestrator cache stats|inspect|clear|threshold`

| Subcommand | Description |
|---|---|
| `stats` | Cache size, total hits, top reused entries |
| `inspect <id>` | Full detail on a single cache entry |
| `clear [--task-type X] [--older-than N]` | Delete entries from Qdrant + SQLite |
| `threshold <value>` | Update similarity threshold in `config.toml` |

---

## Architecture

### Repository layout

```
orchestrator_cli/
├── cli/                    ← Typer CLI entry points
│   ├── commands/           ← connect, accounts, model, route, trace, cache, agent, shell
│   └── tui/               ← Immersive Textual TUI (app, dispatcher, styles)
├── agent/                  ← Sandbox, tool loop, dispatcher, planner, config
├── services/               ← Business logic (connect, account, model, trace, init)
├── core/                   ← Routing pipeline modules
│   ├── router.py           ← 10-step routing pipeline
│   ├── llm_turn.py         ← Agent chat turn (no semantic cache; multi-provider)
│   ├── classifier.py       ← Task type detection (keyword/heuristic)
│   ├── model_selector.py   ← Cost-ranked model selection (pure logic)
│   ├── cost_estimator.py   ← Token count × price math
│   ├── validator.py        ← Output validation
│   ├── semantic_cache.py   ← Qdrant + SQLite cache layer
│   └── reasons.py          ← Route reason code constants
├── providers/              ← Provider connectors and adapters
│   ├── base.py             ← BaseConnector, BaseAdapter, AgentTurnResult
│   ├── anthropic/          ← Messages API + tool calling
│   ├── openai/             ← Chat Completions + tools
│   ├── groq/               ← OpenAI-compatible endpoint + tools
│   └── gemini/             ← Google GenAI (text `route` + `chat_with_tools`)
├── db/                     ← SQLAlchemy ORM + repositories
│   ├── models.py           ← accounts, model_registry, traces, cache_entries, tool_calls
│   └── repositories/       ← CRUD per table
├── embeddings/             ← sentence-transformers wrapper (singleton)
├── schemas/                ← Pydantic models + tools.py (agent tool definitions)
├── utils/                  ← Fernet crypto, Rich console, hashing
└── tests/                  ← pytest (routing, cache, providers, agent, CLI)
```

### Semantic cache design

The cache key is `(embedding vector, task_type, quality)`. Two constraints must both be satisfied for a hit:

1. **Cosine similarity ≥ threshold** (default `0.92`, configurable per task type)
2. **Exact `task_type` + `quality` match** (Qdrant payload filter, never relaxed)

Qdrant stores vectors and lightweight metadata. SQLite stores full response text. They are linked by a shared `uuid4`.

The embedding model (`all-MiniLM-L6-v2`, 384 dimensions) runs entirely locally — no API call is made to check the cache.

### Routing pipeline (10 steps)

1. Normalise prompt (whitespace collapse)
2. Classify task type
3. Embed prompt locally (~5ms)
4. Semantic cache lookup → return immediately on HIT
5. Estimate input token count
6. Select cheapest model satisfying constraints
7. Call provider adapter
8. Validate output
9. Store result in semantic cache
10. Write trace and return

---

## Configuration

`~/.orchestrator/config.toml`:

```toml
[routing]
default_quality = "balanced"
prefer_cheapest = true
fallback_enabled = true

[cache]
enabled = true
ttl_seconds = 86400
similarity_threshold = 0.92
task_thresholds.json_extract = 0.95   # stricter for structured extraction
task_thresholds.reasoning = 0.93
embedding_model = "all-MiniLM-L6-v2"

[cost]
warn_above_usd = 0.01
monthly_budget_usd = 0

[display]
show_cost = true
show_tokens = true
show_route_reason = true
show_cache_similarity = true

[agent]
sandbox_root = "."
max_iterations = 8
max_file_bytes = 1048576
max_subprocess_seconds = 120
allow_shell = false
blocked_shell_patterns = "rm -rf,mkfs,dd if=,:(){:|:&};:"
network_disabled = true   # documented intent; not full OS network isolation
```

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| CLI | Typer |
| Schema validation | Pydantic v2 |
| ORM | SQLAlchemy 2.x |
| Database | SQLite |
| Vector store | Qdrant (embedded, no server) |
| Embedding model | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Config | TOML |
| Credential storage | `cryptography` (Fernet / AES) |
| Console output | `rich` |
| Immersive TUI | `textual` |
| HTTP client | `httpx` |
| Testing | `pytest` + `pytest-asyncio` |

---

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

## Skills

We ship detailed project skills under `skills/` to keep workflows consistent and token-efficient.
Start with:
- `skills/token-efficiency-protocol/SKILL.md`
- `skills/macro-hand-sign-dsl/SKILL.md`
- `skills/cache-safety-playbook/SKILL.md`
- `skills/strict-workflow/SKILL.md`

Tests cover:
- Task classifier (`test_classifier.py`) — 14 parameterised cases
- Cost estimator (`test_cost_estimator.py`) — token estimation and USD math
- Model selector (`test_model_selector.py`) — tier/capability/context constraints
- Semantic cache (`test_semantic_cache.py`) — hit/miss, task_type and quality filters, hit count, clear
- Router integration (`test_router.py`) — mocked provider, dry-run, no-models error path

---

## Roadmap

- [ ] OAuth 2.0 (V2)
- [x] Gemini connector and agent `chat_with_tools`
- [ ] Hard budget enforcement (warn-only in V1)
- [x] Agent / tool-use routing (CLI `orchestrator agent`)
- [x] Immersive TUI shell (default on `orchestrator`, also `orchestrator shell`)
- [ ] FastAPI wrapper
- [ ] Postgres support
