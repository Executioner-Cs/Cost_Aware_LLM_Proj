# Orchestrator V2 Architecture

Status: accepted target. Describes the current architecture, the future architecture, and the migration path between them. Current behavior is the baseline; future concepts are not yet implemented unless stated.

## Current architecture (today)

Layering, intended direction `cli -> services -> core -> providers/db/embeddings/schemas/utils`:

* `cli/`: Typer commands (`cli/commands/`) and a Textual TUI (`cli/tui/`) running the same workflows.
* `services/`: init, connect, account, model, routing, trace orchestration.
* `core/`: `router.py` pipeline, `classifier.py`, `model_selector.py`, `cache.py` (backend selector), `semantic_cache.py` (similarity store used only in semantic mode), `cost_estimator.py`, `llm_turn.py` (agent turn, no cache), `reasons.py`.
* `providers/`: connector plus adapter pairs for Anthropic, OpenAI, Groq, Gemini behind ABCs in `providers/base.py`.
* `db/`: SQLAlchemy models and repositories over SQLite. Tables: `connected_accounts`, `model_registry`, `traces`, `cache_entries` (semantic), `exact_cache`, `tool_calls`. No migration system.
* `embeddings/`: local sentence-transformer embedding, loaded lazily, used only by the semantic cache.
* `agent/`: experimental ReAct loop, path-confined tools, optional shell off by default.

Routing pipeline today (`core/router.py`): normalize, classify, build cache backend, lookup, on miss estimate tokens, select cheapest model within tier and capability constraints, call provider adapter, validate, store, write trace.

Cache tiers today (`core/cache.py`): `get_cache` returns `NoOpCache` (disabled or off), `ExactCache` (default, SQLite only, TTL on read), or `SemanticCacheBackend` (opt-in, lazy heavy imports). This is implemented.

Known coupling debt: `core/router.py` pulls config via `services.init_service`. Do not deepen it. It is slated for `refactor/config-routing-seam`.

## Future architecture (target)

The unit of the system shifts from "provider plus API key" to ModelSource, and routing shifts from "cheapest capable" to "policy over local scorecards."

Target concepts (none are DB models yet):

* ModelSource: a registered source of models. Types: local (for example Ollama), cloud (today's providers), OpenAI-compatible gateway, custom. Identity is the source, not a raw key. Existing providers become one source type.
* RoutingPolicy: a named policy of hard filters, a scoring formula, and a fallback chain.
* TaskSet: a developer's representative tasks with expected outputs or graders.
* BenchmarkRun: an execution of a TaskSet across selected models producing measurements.
* Scorecard: per-model, per-task local results (quality, cost, latency, reliability, JSON and tool success) that feed routing.
* RoutingDecision: the chosen model plus the reasons it was chosen.
* FallbackPlan: the ordered alternatives if the primary fails a filter or a call.
* ExecutionTrace: a richer trace of a route or agent run, beyond today's flat `traces` row.

Target routing flow:

1. Hard filters remove models that cannot satisfy the request (context window, JSON, tools, privacy or local-only).
2. Scoring ranks the survivors using scorecards plus cost, latency, and reliability, under the active policy.
3. The router produces a RoutingDecision and a FallbackPlan, and records an ExecutionTrace.

## Cache tiers (current and forward)

* Default exact-match SQLite cache stays the default. Slim, single-store, TTL on read.
* Semantic cache stays optional. `cache/semantic-cache-v2` hardens it (TTL on lookup, long-prompt safety, SQLite-Qdrant drift handling). Semantic never becomes the default.

## Safe agent mode (later)

Agent mode stays experimental until `security/p0-agent-safety` lands. At minimum that branch enforces or removes `network_disabled`, hardens sandbox confinement, and confirms shell gating. `agent/safe-agent-mode` promotes it only after that.

## Migration path

The migration is incremental and behavior-preserving at each step. See `docs/roadmap/BRANCH_ROADMAP.md` for the branch sequence and definitions of done. Key ordering constraints:

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
