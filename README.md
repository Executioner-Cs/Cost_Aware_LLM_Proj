# Orchestrator CLI

> A local CLI tool for **cost-aware, token-efficient LLM orchestration with semantic caching**.

Connect your existing provider accounts (Anthropic, OpenAI), and the system routes every prompt to the cheapest model that can satisfy the task — with a semantic cache layer that recognises when two differently-worded prompts are asking the same thing.

**The core value proposition**: one command, every model you already pay for, zero wasted tokens, and a cache that actually works in natural language.

---

## Features

- **Semantic cache** — "Summarize this doc" and "Give me a summary of this doc" both hit the same cache entry. Powered by `all-MiniLM-L6-v2` running entirely locally (no API call needed for lookups).
- **Multi-provider routing** — Anthropic and OpenAI models normalised into a unified registry. Cheapest model that satisfies constraints wins.
- **Task classification** — Automatically detects `simple`, `json_extract`, `reasoning`, `vision`, and `tools` task types from the prompt.
- **Cost tracking** — Every request is traced with token counts, USD cost, latency, and cache similarity score.
- **Zero-config vector store** — Qdrant runs embedded (in-process), no Docker or server required.
- **Encrypted credentials** — API keys are Fernet-encrypted before writing to SQLite.

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/Executioner-Cs/Cost_Aware_LLM_Proj.git
cd Cost_Aware_LLM_Proj
pip install -e ".[dev]"
```

### 2. Initialise

```bash
orchestrator init
```

Creates `~/.orchestrator/` with `config.toml`, `orchestrator.db`, and the Qdrant vector store. Also downloads and caches the embedding model on first run.

### 3. Connect a provider

```bash
orchestrator connect anthropic   # prompts for API key
orchestrator connect openai      # prompts for API key
```

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
Set up the home directory, SQLite database, Qdrant collection, and warm up the embedding model.

### `orchestrator connect <provider>`
Connect an Anthropic or OpenAI account using a Personal Access Token (API key). Validates the key and populates the model registry.

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
│   └── commands/           ← connect, accounts, model, route, trace, cache
├── services/               ← Business logic (connect, account, model, trace, init)
├── core/                   ← Routing pipeline modules
│   ├── router.py           ← 10-step routing pipeline
│   ├── classifier.py       ← Task type detection (keyword/heuristic)
│   ├── model_selector.py   ← Cost-ranked model selection (pure logic)
│   ├── cost_estimator.py   ← Token count × price math
│   ├── validator.py        ← Output validation
│   ├── semantic_cache.py   ← Qdrant + SQLite cache layer
│   └── reasons.py          ← Route reason code constants
├── providers/              ← Provider connectors and adapters
│   ├── base.py             ← BaseConnector, BaseAdapter ABCs
│   ├── anthropic/          ← Messages API
│   └── openai/             ← Chat Completions API
├── db/                     ← SQLAlchemy ORM + repositories
│   ├── models.py           ← 4 tables: accounts, models, traces, cache_entries
│   └── repositories/       ← CRUD per table
├── embeddings/             ← sentence-transformers wrapper (singleton)
├── schemas/                ← Pydantic v2 request/response models
├── utils/                  ← Fernet crypto, Rich console, hashing
└── tests/                  ← pytest suite (classifier, cost, selector, cache, router)
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
| HTTP client | `httpx` |
| Testing | `pytest` + `pytest-asyncio` |

---

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Tests cover:
- Task classifier (`test_classifier.py`) — 14 parameterised cases
- Cost estimator (`test_cost_estimator.py`) — token estimation and USD math
- Model selector (`test_model_selector.py`) — tier/capability/context constraints
- Semantic cache (`test_semantic_cache.py`) — hit/miss, task_type and quality filters, hit count, clear
- Router integration (`test_router.py`) — mocked provider, dry-run, no-models error path

---

## Roadmap

- [ ] OAuth 2.0 (V2)
- [ ] Gemini connector
- [ ] Hard budget enforcement (warn-only in V1)
- [ ] Agent / tool-use routing
- [ ] FastAPI wrapper
- [ ] Postgres support
