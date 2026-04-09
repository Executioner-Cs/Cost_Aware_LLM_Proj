# CLAUDE.md — Orchestrator CLI

> Canonical reference for Claude (and any LLM dev assistant) working in this codebase.
> Update this file whenever architecture, commands, or conventions change.

---

## What this is

A **local CLI tool for cost-aware, token-efficient LLM orchestration with semantic caching**, plus an optional **sandboxed agent** that runs multi-step tool loops while still picking the cheapest suitable model **across every connected account**.

Users connect provider accounts (**Anthropic**, **OpenAI**, **Groq**, **Google Gemini**). The system discovers models, normalizes them into one registry, and routes each prompt (and each agent LLM step) to the cheapest model that satisfies constraints — with a semantic cache on the single-shot `route` path that recognises when two differently-worded prompts are asking the same thing.

**The core value**: one command, every model you already pay for, zero wasted tokens where caching is safe, and a cache that actually works in natural language. Agent turns intentionally **skip** semantic cache (non-deterministic transcripts).

---

## Why semantic cache instead of exact cache

Exact (hash-based) cache: "Summarize this doc" and "Give me a summary of this doc" are two different keys. Cache miss every time.

Semantic cache: both prompts embed to nearly identical vectors. One lookup, one hit.

For an LLM router this is the right default — users rephrase, paraphrase, and copy-paste with minor edits constantly. Exact cache captures almost nothing real. Semantic cache captures the actual repetition patterns.

**The constraint that makes it harder here**: similarity alone is not enough to serve a cached result. A hit is only valid if:
1. Cosine similarity ≥ threshold (default 0.92)
2. `task_type` matches exactly — never serve a `json_extract` result to a `reasoning` query
3. `quality` tier is compatible — never serve a `cheap` result to a `best` request

The cache key is `(embedding vector, task_type, quality)`. Qdrant handles vector lookup. SQLite stores payload.

---

## Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Typer, async support, ecosystem |
| CLI framework | Typer | Clean, type-safe, fast to build |
| Schema validation | Pydantic v2 | Uniform request/response shapes |
| ORM | SQLAlchemy 2.x | Session-based |
| Database | SQLite | Payload store for cache + traces + accounts |
| Vector store | Qdrant (local, embedded mode) | Semantic cache index, runs in-process, no server needed |
| Embedding model | `sentence-transformers` (`all-MiniLM-L6-v2`) | Fast, local, 384-dim, no API call needed for cache lookup |
| Config | TOML via `tomllib` | Human-readable |
| Credential storage | `cryptography` (Fernet) | AES encryption for session tokens |
| Console output | `rich` | Tables, panels, spinners |
| Immersive TUI | `textual` | Default interactive mode (`orchestrator`) + explicit `orchestrator shell` |
| Interactive setup UI | `questionary` | Arrow-key provider selection after `orchestrator init` |
| HTTP client | `httpx` | Used by all provider adapters |
| Testing | `pytest` + `pytest-asyncio` | Standard |

**Qdrant embedded mode**: runs inside the process via `qdrant-client` (path-based local storage; no separate `[local]` pip extra in current releases). No Docker, no daemon, no network. Collection stored at `.orchestrator/qdrant/`. Zero-config for the user.

**Why `all-MiniLM-L6-v2`**: 384 dimensions (small, fast), runs entirely locally, strong semantic similarity for short-to-medium text. The model is downloaded once on first `orchestrator init` and cached by `sentence-transformers`. No API call required for cache lookups — this is critical; you cannot call an LLM to check if you should call an LLM.

---

## Repository layout

```
orchestrator_cli/
├── CLAUDE.md
├── pyproject.toml
├── README.md
├── .env.example
│
├── cli/
│   ├── main.py
│   └── commands/
│       ├── connect.py            ← `orchestrator connect <provider>`
│       ├── accounts.py           ← `orchestrator accounts list|sync|disconnect`
│       ├── model.py              ← `orchestrator model list`
│       ├── route.py              ← `orchestrator route <prompt> [flags]`
│       ├── trace.py              ← `orchestrator trace list|show`
│       ├── cache.py              ← `orchestrator cache stats|clear|inspect|threshold`
│       ├── agent.py              ← `orchestrator agent run|edit|explain|fix-tests|refactor`
│       └── shell.py             ← `orchestrator shell` (explicit TUI alias)
│
├── cli/tui/
│   ├── app.py                    ← Textual App: SessionState bootstrap, header status, RichLog, Input
│   ├── dispatcher.py             ← Parses TUI commands → calls services, captures output
│   └── style.tcss                ← Textual CSS for layout
│
├── agent/
│   ├── config.py                 ← `[agent]` TOML → AgentConfig
│   ├── dispatcher.py             ← dispatch_tool(name, args) → sandboxed execution
│   ├── loop.py                   ← run_agent_loop (ReAct-style)
│   ├── planner.py                ← optional planning preamble / cheap route()
│   ├── sandbox.py                ← path confinement under sandbox_root
│   ├── tool_logging.py           ← optional SQLite tool_calls rows
│   └── tools/
│       ├── file_io.py
│       ├── search.py
│       └── execution.py          ← python / pytest / optional shell (guarded)
│
├── services/
│   ├── init_service.py
│   ├── connect_service.py
│   ├── account_service.py
│   ├── model_service.py
│   ├── routing_service.py
│   └── trace_service.py
│
├── core/
│   ├── router.py                 ← main single-shot routing pipeline
│   ├── llm_turn.py               ← agent chat turn: multi-account tool model pick (no cache)
│   ├── classifier.py             ← task type detection
│   ├── model_selector.py         ← cost+capability ranked selection
│   ├── cost_estimator.py         ← token count × price math
│   ├── validator.py              ← output validation
│   ├── semantic_cache.py         ← semantic cache read/write (Qdrant + SQLite)
│   └── reasons.py                ← reason code constants
│
├── providers/
│   ├── base.py                   ← BaseAdapter.chat_with_tools (default: NotImplemented)
│   ├── anthropic/
│   │   ├── connector.py
│   │   └── adapter.py            ← Messages API + tool use
│   ├── openai/
│   │   ├── connector.py
│   │   └── adapter.py            ← Chat Completions + tools
│   ├── groq/
│   │   ├── connector.py
│   │   └── adapter.py            ← OpenAI-compatible + tools
│   └── gemini/
│       ├── connector.py
│       └── adapter.py            ← text generation + chat_with_tools (google-genai)
│
├── db/
│   ├── session.py
│   ├── models.py                 ← ORM: accounts, model_registry, traces, cache_entries, tool_calls
│   └── repositories/
│       ├── accounts.py
│       ├── models.py
│       ├── traces.py
│       ├── cache.py              ← cache_entries CRUD
│       └── tool_calls.py
│
├── embeddings/
│   ├── embedder.py               ← loads sentence-transformers model, exposes embed()
│   └── model_cache.py            ← singleton: load once, reuse across calls
│
├── schemas/
│   ├── account.py
│   ├── routing.py                ← RouteRequest, RouteResult
│   ├── trace.py
│   └── tools.py                  ← AGENT_TOOLS_OPENAI (wire format; adapters translate)
│
├── utils/
│   ├── crypto.py
│   ├── console.py
│   └── hashing.py                ← still used for trace IDs, not cache keys
│
└── tests/
    ├── test_classifier.py
    ├── test_router.py
    ├── test_semantic_cache.py
    ├── test_agent_*.py
    ├── test_llm_turn_providers.py
    ├── test_providers_groq_gemini.py
    └── …                         ← see tests/ for full list
```

---

## Semantic cache architecture

### Data flow

```
prompt
  │
  ▼
embedder.embed(prompt)              ← local, ~5ms, no API call
  │
  ▼
qdrant.search(                      ← ANN search in embedded Qdrant
  collection="cache",
  query_vector=embedding,
  filter={task_type: X, quality: Y},
  limit=1,
  score_threshold=0.92
)
  │
  ├── score ≥ 0.92 → HIT
  │     pull payload_id from Qdrant result
  │     fetch response_text from SQLite cache_entries by payload_id
  │     return cached result
  │
  └── score < 0.92 → MISS
        call provider
        get response
        embed prompt (already done, reuse vector)
        qdrant.upsert(vector=embedding, payload={task_type, quality, sqlite_id})
        sqlite INSERT into cache_entries
        return fresh result
```

### Why Qdrant + SQLite (not Qdrant alone)

Qdrant stores vectors and lightweight metadata (task_type, quality, sqlite_id). It cannot efficiently store large text blobs like full LLM responses. SQLite stores the actual response text, token counts, and cost metadata. The two are linked by `sqlite_id` stored as a Qdrant payload field.

On a cache hit:
1. Qdrant returns the nearest vector match + its payload (`sqlite_id`)
2. SQLite fetches the full response by `sqlite_id`

This keeps Qdrant lean and fast while SQLite handles the heavy payload.

### Similarity threshold

Default: **0.92 cosine similarity** (configurable in `config.toml`).

Empirically:
- 0.98+ = near-exact wording only (too strict, barely better than exact hash)
- 0.92–0.97 = same question, different phrasing (right zone)
- 0.85–0.91 = related but not the same question (too loose, wrong answers)
- < 0.85 = different topic (definitely miss)

The threshold should be tunable per task type. `json_extract` warrants a higher threshold (0.95+) because field extraction is brittle — "extract the invoice number" and "extract the invoice date" are ~0.88 similar but need completely different answers.

### Hard filters (never relaxed by similarity score)

These are Qdrant payload filters applied before ANN search:

```python
qdrant_filter = Filter(
    must=[
        FieldCondition(key="task_type", match=MatchValue(value=task_type)),
        FieldCondition(key="quality",   match=MatchValue(value=quality)),
    ]
)
```

A `reasoning` result is never served to a `json_extract` request, regardless of how similar the prompt vectors are.

### `core/semantic_cache.py` interface

```python
class SemanticCache:

    def __init__(self, qdrant_path: Path, sqlite_session: Session):
        self.qdrant = QdrantClient(path=str(qdrant_path))
        self.session = sqlite_session
        self._ensure_collection()

    def lookup(
        self,
        embedding: list[float],
        task_type: str,
        quality: str,
    ) -> CacheResult | None:
        """
        Returns CacheResult if a semantically similar entry exists above threshold.
        Returns None on miss.
        """

    def store(
        self,
        embedding: list[float],
        task_type: str,
        quality: str,
        response_text: str,
        provider: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Writes vector to Qdrant + payload to SQLite.
        Linked by a shared uuid4 (sqlite_id stored in Qdrant payload).
        """

    def _ensure_collection(self) -> None:
        """Creates Qdrant collection if it doesn't exist. Called on init."""
```

### Qdrant collection config

```python
qdrant.recreate_collection(
    collection_name="semantic_cache",
    vectors_config=VectorParams(
        size=384,           # all-MiniLM-L6-v2 output dimension
        distance=Distance.COSINE,
    ),
)
```

Payload fields per point:
- `sqlite_id` (str) — foreign key into SQLite `cache_entries.id`
- `task_type` (str) — used as hard filter
- `quality` (str) — used as hard filter
- `created_at` (str) — ISO 8601, for TTL-based cleanup

---

## SQLite schema (source of truth)

### `connected_accounts`

```sql
CREATE TABLE connected_accounts (
  id                TEXT PRIMARY KEY,
  provider          TEXT NOT NULL,
  display_name      TEXT,
  email             TEXT,
  auth_method       TEXT NOT NULL,       -- 'oauth' | 'pat' | 'session_cookie'
  encrypted_token   TEXT NOT NULL,
  encrypted_refresh TEXT,
  token_expires_at  TEXT,
  plan              TEXT,
  status            TEXT DEFAULT 'active',
  connected_at      TEXT NOT NULL,
  last_synced_at    TEXT
);
```

### `model_registry`

```sql
CREATE TABLE model_registry (
  id                  TEXT PRIMARY KEY,
  account_id          TEXT REFERENCES connected_accounts(id),
  provider            TEXT NOT NULL,
  external_model_id   TEXT NOT NULL,
  display_name        TEXT,
  tier                TEXT NOT NULL,      -- 'small' | 'balanced' | 'large'
  context_window      INTEGER,
  cost_per_1m_input   REAL,
  cost_per_1m_output  REAL,
  supports_json       INTEGER DEFAULT 0,
  supports_tools      INTEGER DEFAULT 0,
  supports_vision     INTEGER DEFAULT 0,
  enabled             INTEGER DEFAULT 1,
  discovered_at       TEXT NOT NULL
);
```

### `traces`

```sql
CREATE TABLE traces (
  id                  TEXT PRIMARY KEY,
  prompt_preview      TEXT,
  task_type           TEXT,
  route_reason        TEXT,
  provider            TEXT,
  model_external_id   TEXT,
  cache_hit           INTEGER DEFAULT 0,
  cache_similarity    REAL,              -- cosine similarity score, null on miss
  input_tokens        INTEGER,
  output_tokens       INTEGER,
  estimated_cost_usd  REAL,
  latency_ms          INTEGER,
  status              TEXT DEFAULT 'ok',
  error_message       TEXT,
  created_at          TEXT NOT NULL
);
```

Note `cache_similarity` — stored on every hit so you can inspect and tune the threshold.

### `cache_entries`
SQLite payload store. Qdrant holds the vector; this holds the text.

```sql
CREATE TABLE cache_entries (
  id            TEXT PRIMARY KEY,       -- uuid4, same as Qdrant point ID
  response_text TEXT NOT NULL,
  task_type     TEXT NOT NULL,
  quality       TEXT NOT NULL,
  provider      TEXT,
  model_id      TEXT,
  input_tokens  INTEGER,
  output_tokens INTEGER,
  hit_count     INTEGER DEFAULT 0,      -- incremented on each cache hit
  created_at    TEXT NOT NULL,
  last_hit_at   TEXT
);
```

`hit_count` and `last_hit_at` enable cache analytics via `orchestrator cache stats`.

### `tool_calls`

Optional structured log of agent (or future orchestrator) tool invocations.

```sql
CREATE TABLE tool_calls (
  id           TEXT PRIMARY KEY,
  trace_id     TEXT REFERENCES traces(id),
  name         TEXT NOT NULL,
  args_json    TEXT NOT NULL,
  result_json  TEXT,
  duration_ms  INTEGER,
  created_at   TEXT NOT NULL
);
```

---

## Full routing pipeline (`core/router.py`)

```
1. Normalize prompt
   → strip leading/trailing whitespace, collapse internal whitespace

2. Classify task
   → classifier.py: keyword + heuristic rules
   → 'simple' | 'json_extract' | 'reasoning' | 'vision' | 'tools'

3. Embed prompt
   → embedder.embed(normalized_prompt)
   → local sentence-transformers call, ~5ms
   → 384-dim float vector
   → NOTE: embed BEFORE cache lookup, reuse vector on store

4. Semantic cache lookup
   → semantic_cache.lookup(embedding, task_type, quality)
   → Qdrant ANN search with hard payload filters
   → if similarity ≥ threshold AND filters match: HIT
        fetch payload from SQLite by sqlite_id
        update hit_count + last_hit_at
        write trace (cache_hit=1, cache_similarity=score, cost=$0.00)
        return CacheResult immediately — skip steps 5–8

5. Estimate input token count
   → cost_estimator.count_tokens(prompt, candidate_models)

6. Select optimal model
   → model_selector.select(task_type, quality, required_caps, input_tokens)
   → cost-ranked: cheapest model satisfying all hard constraints wins

7. Call provider adapter
   → adapter.generate(prompt, model_id, options)
   → returns GenerateResult with actual token counts + latency

8. Validate output
   → non-empty check
   → JSON parse check if task_type == 'json_extract'
   → on failure: trace status='validation_failed', raise ValidationError

9. Store in semantic cache
   → semantic_cache.store(embedding, task_type, quality, response, ...)
   → Qdrant upsert (vector + payload)
   → SQLite INSERT (full payload)

10. Write trace
    → full metadata: tokens, actual cost, latency, model, route_reason
    → return RouteResult to CLI layer
```

---

## Agent stack (`agent/` + `core/llm_turn.py`)

- **Semantic cache**: **not** used for agent LLM turns. Message history and tool results are unique per run; only `orchestrator route` uses the cache pipeline above.
- **Tool definitions**: Single source in `schemas/tools.py` (`AGENT_TOOLS_OPENAI`). OpenAI and Groq use native function calling; Anthropic’s adapter maps the same shapes to the Messages API.
- **Model selection for each turn**: `agent_chat_turn()` in `core/llm_turn.py` lists **all** enabled models with `supports_tools`, intersects with **`AGENT_TOOL_PROVIDERS`** (`openai`, `anthropic`, `groq`, `gemini`), then `model_selector` picks the cheapest that fits context + quality.
- **Execution**: `agent/dispatcher.py` routes tool names to `agent/tools/*` under `sandbox_root` from `[agent]` config. Shell is **off** by default; optional allow-list style blocking via `blocked_shell_patterns`.
- **Persistence**: Tool calls may be written through `db/repositories/tool_calls.py`.

---

## Embedder (`embeddings/embedder.py`)

```python
from sentence_transformers import SentenceTransformer
from functools import lru_cache

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM   = 384

@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Load once, reuse. ~22MB model, loads in ~200ms on first call."""
    return SentenceTransformer(EMBEDDING_MODEL)

def embed(text: str) -> list[float]:
    model = get_embedder()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()
```

Key decisions:
- `normalize_embeddings=True` ensures vectors are unit-normalized, making cosine similarity = dot product (faster Qdrant search)
- `lru_cache(maxsize=1)` — model loaded once per process, not per call
- Model downloaded on first `orchestrator init` via `model.encode("warmup")` in init_service
- No batching needed for CLI use (one prompt at a time)

---

## Cache CLI commands

### `orchestrator cache stats`

```
Semantic cache statistics
─────────────────────────
Total entries    : 1,247
Total hits       : 4,832
Hit rate (7d)    : 34.2%
Avg similarity   : 0.961
Lowest threshold hit: 0.921

Top reused entries:
  "Summarize the weekly report"     → 47 hits   last: 3m ago
  "Extract invoice number and date" → 31 hits   last: 1h ago
  "Rewrite this email professionally"→ 28 hits  last: 2h ago

Estimated cost saved (7d): $0.847
```

### `orchestrator cache inspect <entry-id>`

Shows the stored response, original prompt, similarity scores of recent hits, and which model originally produced it.

### `orchestrator cache clear [--task-type <type>] [--older-than <days>]`

Removes entries from both Qdrant and SQLite. Filters optional.

### `orchestrator cache threshold <value>`

Adjusts similarity threshold in `config.toml`. Effective immediately for subsequent calls.

---

## CLI commands reference (full)

### `orchestrator connect <provider>`

```bash
orchestrator connect anthropic
orchestrator connect openai
orchestrator connect groq
orchestrator connect gemini
```

Auth flow: API key (PAT) in V0; OAuth in V2. Pulls model list. Populates `model_registry`. Only **connected** providers participate in routing.

API key lookup precedence:
1. `--api-key` (if provided)
2. repo-root `.env` / environment variables (loaded via `python-dotenv`)
3. hidden terminal prompt

Environment variables:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GROQ_API_KEY`
- `GEMINI_API_KEY`

### `orchestrator accounts list|sync|disconnect`

Manage connected provider accounts.

### `orchestrator model list`

```
provider    model                  tier      ctx     $/1M in   $/1M out
anthropic   claude-haiku-4-5       small     200k    $0.25     $1.25
anthropic   claude-sonnet-4-6      balanced  200k    $3.00     $15.00
openai      gpt-4o-mini            small     128k    $0.15     $0.60
openai      gpt-4o                 balanced  128k    $2.50     $10.00
```

### `orchestrator route <prompt>`

```bash
orchestrator route "Summarize this meeting note"
orchestrator route "Extract line items as JSON: ..." --task json_extract
orchestrator route "Reason through this tradeoff" --quality best
orchestrator route "What would this cost?" --dry-run
```

**Output (cache miss)**:
```
Task       : simple
Route      : simple_task_cheapest_model
Provider   : openai
Model      : gpt-4o-mini
Cache      : miss
Tokens     : 48 in / 112 out
Cost       : $0.000083
Latency    : 0.9s

Answer
------
[response]
```

**Output (semantic cache hit)**:
```
Task       : simple
Route      : semantic_cache_hit
Cache      : HIT  (similarity: 0.961)
Cost       : $0.000000
Latency    : 0.012s

Answer
------
[cached response]
```

### `orchestrator` (default immersive mode / hybrid entrypoint)

**Hybrid behaviour** (implemented in `cli/main.py` callback):
- `orchestrator` (no args, interactive TTY) → launches immersive Textual TUI.
- `orchestrator` (no args, non-interactive) → prints help and exits.
- `orchestrator <subcommand> …` → runs that subcommand directly (unchanged).

`orchestrator shell` is an explicit alias that always launches the TUI regardless of detection.

```bash
orchestrator              # interactive TTY → immersive TUI
orchestrator shell        # explicit alias — same result
```

Inside the shell, commands are entered without the `orchestrator` prefix:

```
orchestrator > help                   # list commands
orchestrator > connect openai sk-...  # connect with inline key
orchestrator > model list             # browse models
orchestrator > route "Summarize this" # route a prompt
orchestrator > cache stats            # cache analytics
orchestrator > agent run "Fix tests"  # agent loop
orchestrator > exit                   # or Ctrl+Q
```

**Session bootstrap**: on startup, the TUI hydrates a `SessionState` — config, DB/Qdrant readiness, account/model summaries. The header subtitle shows a live status line (provider count, model count, cache on/off, quality). State refreshes automatically after `connect`, `init`, or `accounts` commands.

**Key bindings**: `Ctrl+Q` = quit, `Ctrl+C` = clear input (app stays alive), `Escape` = clear input.

The TUI dispatches to the same service layer as the regular CLI commands. Connect prompts are replaced by inline arguments (`connect <provider> <key>`). Status spinners are suppressed in captured output.

**Architecture**: `cli/tui/app.py` (Textual App with `SessionState` + `bootstrap_state()`), `cli/tui/dispatcher.py` (command parser → service calls, captures Rich console output via `console.capture()` with ANSI preservation), `cli/tui/style.tcss` (layout CSS).

### `orchestrator agent …`

Multi-step tool loop with sandboxed file I/O, search, Python/pytest, and optional shell.

```bash
orchestrator agent run "Implement feature X in src/foo.py"
orchestrator agent edit path/to/file.py "Add docstrings"
orchestrator agent explain path/to/file.py
orchestrator agent fix-tests
orchestrator agent refactor src/ "Extract shared helper"
```

Common flags on `run`: `--quality`, `--max-iterations`, `--plan`, `--plan-llm`. See `orchestrator agent run --help`.

### `orchestrator trace list|show`

Traces include `cache_similarity` score on hits so you can see exactly why something was served from cache.

---

## Reason codes (`core/reasons.py`)

```python
SEMANTIC_CACHE_HIT             = "semantic_cache_hit"
SIMPLE_TASK_CHEAPEST           = "simple_task_cheapest_model"
REASONING_TASK_BALANCED        = "reasoning_task_balanced_model"
JSON_EXTRACT_JSON_CAPABLE      = "json_extract_json_capable_model"
BEST_QUALITY_FORCED            = "best_quality_forced_large_model"
CHEAP_QUALITY_FORCED           = "cheap_quality_forced_small_model"
FALLBACK_SECONDARY_PROVIDER    = "fallback_to_secondary_provider"
PROVIDER_GENERATION_FAILED     = "provider_generation_failed"
VALIDATION_FAILED              = "validation_failed"
NO_SUITABLE_MODEL              = "no_suitable_model_found"
TOKEN_LIMIT_EXCEEDED           = "input_exceeds_all_context_windows"
```

---

## Config file (`.orchestrator/config.toml`)

```toml
[routing]
default_quality = "balanced"
prefer_cheapest = true
fallback_enabled = true

[cache]
enabled = true
ttl_seconds = 86400                    # 24h default TTL
similarity_threshold = 0.92            # global default
task_thresholds.json_extract = 0.95   # stricter for structured extraction
task_thresholds.reasoning = 0.93      # slightly stricter for reasoning
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
network_disabled = true
```

`network_disabled` documents intent for future hardening; it is not full OS-level network isolation.

---

## `orchestrator init` — what it sets up

```
.orchestrator/
├── config.toml          ← default config written
├── orchestrator.db      ← SQLite file, all tables created (including tool_calls)
└── qdrant/              ← Qdrant embedded store directory
    └── collection/
        └── semantic_cache/
```

On first init, `init_service.py` also warms up the embedding model:
```python
embed("warmup")   # triggers sentence-transformers download if not cached
```

This prevents a surprise 200ms delay on the first `orchestrator route` call.

After the success panel, init attempts an interactive provider handoff:
- If terminal is interactive and `questionary` is available: show arrow-key picker (`openai`, `anthropic`, `gemini`, `groq`) and run `connect` immediately for the selection.
- If non-interactive, unavailable, or cancelled: print explicit fallback `orchestrator connect <provider>` commands and exit without error.
- Interactivity gating checks `sys.stdin.isatty()`, `sys.stdout.isatty()`, and Rich console terminal support before launching picker.
- If `questionary` is missing, print dependency guidance to install extras in active venv: `pip install -e ".[dev]"`.
- API key behavior during init handoff stays aligned with connect UX: env/dotenv first, then hidden prompt fallback.

---

## Sprint build order

### Sprint 1 — Foundation
1. Scaffold repo, pyproject.toml, folder structure
2. `db/models.py` + `db/session.py`
3. `orchestrator init` — dir, config, SQLite `create_all`, Qdrant collection init, embedding warmup
4. `providers/base.py` — ABCs + shared types

### Sprint 2 — Account connection
5. `providers/anthropic/connector.py` + `providers/openai/connector.py` (PAT)
6. `services/connect_service.py` + `orchestrator connect`
7. `services/model_service.py` + `orchestrator model list`
8. `orchestrator accounts list|sync|disconnect`

### Sprint 3 — Embedding + semantic cache
9. `embeddings/embedder.py` — sentence-transformers wrapper
10. `core/semantic_cache.py` — Qdrant lookup + SQLite payload store
11. Tests: `test_semantic_cache.py` with synthetic similar/dissimilar prompt pairs

### Sprint 4 — Routing engine
12. `core/classifier.py`
13. `core/cost_estimator.py`
14. `core/model_selector.py`
15. `providers/anthropic/adapter.py` + `providers/openai/adapter.py`
16. `core/validator.py`
17. `core/router.py` — full pipeline with semantic cache integrated
18. `orchestrator route`

### Sprint 5 — Observability
19. `services/trace_service.py` + `orchestrator trace list|show`
20. `orchestrator cache stats|inspect|clear|threshold`

### Sprint 6 — Tests + polish
21. Full test suite
22. `--dry-run` flag
23. Cost warnings
24. Embedding model download UX (progress bar on first init)

---

## Key conventions

- **Virtual environment**: Use a project-local venv (e.g. `.venv/`). **Activate it before any `pip install` or dependency change** so packages and tests use the same interpreter. Do not install project dependencies into the system Python when working on this repo.
- **Macro expander (agent)**: `orchestrator agent` supports a local inline macro DSL at the start of the goal (e.g. `{BRPR,VENV,CX:2K} ...`). Macros expand into system-prompt constraints without spending model tokens. Implementation lives in `agent/macro_expander.py` and is applied in `agent/loop.py`.
- **Skills**: Keep recurring workflows as detailed skills under `skills/<name>/SKILL.md` (token efficiency, macro DSL, cache safety, strict workflow).
- IDs are `uuid4` strings stored as `TEXT`
- Timestamps are ISO 8601 UTC: `datetime.utcnow().isoformat() + 'Z'`
- Tokens/credentials are always Fernet-encrypted before SQLite write
- Embeddings are unit-normalized (L2 norm = 1) so cosine similarity = dot product
- The embedder is a process-level singleton — never instantiate `SentenceTransformer` more than once
- `model_selector.py` is pure logic — no I/O, no DB access
- `semantic_cache.py` is the only module that touches Qdrant
- `db/repositories/cache.py` is the only module that reads/writes `cache_entries` in SQLite
- These two are always called together by `core/router.py` — never independently from other modules
- `db/repositories/tool_calls.py` owns `tool_calls` rows; agent code may log through it
- Agent LLM turns go through `core/llm_turn.py` + provider `chat_with_tools`, not `router.route()`’s cache path
- Reason codes always imported from `core/reasons.py`
- `rich` for all terminal output — no bare `print()`
- **TUI dispatcher** (`cli/tui/dispatcher.py`) captures Rich console output via `console.capture()` with `_force_terminal=True` for ANSI preservation, and `console.status` is replaced with a no-op context manager during capture. Runs in a Textual worker thread; results posted back to the main thread via `call_from_thread`.
- **Hybrid root command** (`cli/main.py`): `_is_interactive_tty()` detects whether to launch TUI or show help when no subcommand is given. TTY detection checks `sys.stdin.isatty()` and `sys.stdout.isatty()`.
- **Session state** (`cli/tui/app.py`): `bootstrap_state()` loads config, checks DB/Qdrant, and collects provider/model counts. `_refresh_state()` is called after state-mutating commands (`connect`, `init`, `accounts`) to keep the header subtitle current.

---

## What is out of scope for V0–V1

- OAuth 2.0 (V0 uses API keys / PAT everywhere)
- Hard budget enforcement (warn-only in V1)
- FastAPI wrapper
- Web UI
- Postgres
- MCP server
- Strong subprocess **network** isolation (`network_disabled` is documented only for now)
