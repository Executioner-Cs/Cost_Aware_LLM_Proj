# Orchestrator V2 Architecture

Status: accepted target. Describes the current architecture, the future architecture, and the migration path between them. Current behavior is the baseline; future concepts are not yet implemented unless stated.

## Current architecture (today)

Layering, intended direction `cli -> services -> core -> providers/db/embeddings/schemas/utils`:

* `cli/`: Typer commands (`cli/commands/`) and a Textual TUI (`cli/tui/`) running the same workflows.
* `services/`: init, connect, account, model, routing, trace orchestration.
* `core/`: `router.py` pipeline, `classifier.py`, `model_selector.py`, `cache.py` (backend selector: exact or off), `cost_estimator.py`, `llm_turn.py` (agent turn, no cache), `reasons.py`. The legacy `semantic_cache.py` was removed.
* `providers/`: connector plus adapter pairs for Anthropic, OpenAI, Groq, Gemini behind ABCs in `providers/base.py`. `providers/source.py` wraps each provider as a `ModelSource`; the routing generate path goes through it. See "ModelSource abstraction".
* `db/`: SQLAlchemy models and repositories over SQLite. Tables: `connected_accounts`, `model_registry`, `traces`, `exact_cache`, `tool_calls`, and `cache_entries` (legacy semantic table, kept to preserve schema and old data; no longer written). No migration system.
* The `embeddings/` package and Qdrant vector store were removed with the legacy semantic cache.
* `agent/`: experimental ReAct loop, path-confined tools, optional shell off by default.

Routing pipeline today (`core/router.py`): normalize, classify, build cache backend, lookup, on miss estimate tokens, select cheapest model within tier and capability constraints, call provider adapter, validate, store, write trace.

Cache today (`core/cache.py`): `get_cache` returns `NoOpCache` (disabled or off) or `ExactCache` (default, SQLite only, TTL on read). `cache.mode = "semantic"` raises a clear error: the legacy semantic backend was removed.

Known coupling debt: `core/router.py` pulls config via `services.init_service`. Do not deepen it. It is slated for a future config-routing refactor.

## Future architecture (target)

The unit of the system shifts from "provider plus API key" to ModelSource, and routing shifts from "cheapest capable" to "policy over local scorecards."

Target concepts (status noted per concept):

* ModelSource: a registered source of models. Types: local (for example Ollama), cloud (today's providers), OpenAI-compatible gateway, custom. Identity is the source, not a raw key. Existing providers become one source type.
  * ModelSource abstraction (status): the seam has landed in `providers/source.py`. It wraps the four cloud providers plus local Ollama and OpenAI-compatible HTTP endpoints (`connect --base-url`), with `source_type` and `base_url` stored on `ConnectedAccount`. `list_models` and `generate` delegate per source; the routing generate path calls `get_model_source(...).generate(...)`. Source-as-primary-identity (replacing provider plus account) and hosted-gateway / custom sources are still future.
* RoutingPolicy: a named policy of hard filters, a scoring formula, and a fallback chain.
* TaskSet: a developer's representative tasks with expected outputs or graders. Status: implemented as the `task_sets` + `benchmark_tasks` tables (`orchestrator benchmark create` / `add-task`).
* BenchmarkRun: an execution of a TaskSet across selected models producing measurements. Status: implemented as the `benchmark_runs` table (`orchestrator benchmark run`).
* Scorecard: per-model local results that will feed routing. Status: implemented as the `scorecards` table with deterministic scoring only (exact / contains / json_valid), recording pass rate, average latency, and average cost. Latency/reliability as routing dimensions and any LLM-as-judge are not in v1. Benchmark-driven routing is wired in a subsequent change: the policy engine prefers models that scored well on the relevant task set, with an explicit fallback when no scorecard exists, so routing decisions are grounded in the user's own measurements.
* RoutingDecision: the chosen model plus the reasons it was chosen.
* FallbackPlan: the ordered alternatives if the primary fails a filter or a call.
* ExecutionTrace: a richer trace of a route or agent run, beyond today's flat `traces` row.

Target routing flow:

1. Hard filters remove models that cannot satisfy the request (context window, JSON, tools, privacy or local-only).
2. Scoring ranks the survivors using scorecards plus cost, latency, and reliability, under the active policy.
3. The router produces a RoutingDecision and a FallbackPlan, and records an ExecutionTrace.

## Cache tiers (current and forward)

* Exact-match SQLite cache stays the default and, today, the only implemented cache. Slim, single-store, TTL on read.
* The legacy heavy semantic cache (embeddings + Qdrant) was removed. A future lighter semantic cache may replace it (candidates: sqlite-vec, provider embeddings, FastEmbed). It would stay optional and never become the default. Not implemented.

## Safe agent mode (later)

Agent mode stays experimental until the agent-safety hardening lands. At minimum that work enforces or removes `network_disabled`, hardens sandbox confinement, and confirms shell gating. Agent mode is promoted only after that.

## Migration path

The migration is incremental and behavior-preserving at each step. Key ordering constraints:

* Slim dependencies and stabilize the cache before building new subsystems.
* Fix agent safety and registry integrity before feature growth.
* Clean the config-routing seam before introducing ModelSource, so the abstraction lands on clean config flow.
* Introduce ModelSource before adding new sources.
* Build the policy engine before benchmarks, but design the policy to consume scorecards so benchmarks plug in without a rewrite.
* Each new model or concept must wrap existing behavior without breaking current routing, proven by tests.

## Non-negotiables carried into V2

* Local-first. No required hosted services. No telemetry by default.
* No heavy dependencies on the base route path.
* Cache correctness over hit rate.
* No provider-count chase. Sources and scorecards are the product, not breadth.
* No documented feature that is not implemented.
