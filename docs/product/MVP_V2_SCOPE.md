# MVP V2 Scope

Status: accepted. Defines the smallest V2 that proves the product thesis, and what is deliberately out of scope or delayed.

## The thesis the MVP must prove

A developer can register models, benchmark them on their own tasks, and have routing decisions driven by those local measurements with a clear explanation of why each model was chosen.

## Real MVP (the minimum that proves it)

1. ModelSource abstraction with at least two source types working: existing cloud providers, and one local or OpenAI-compatible source (Ollama or an OpenAI-compatible endpoint).
2. TaskSet: a developer can define a small set of representative tasks with expected outputs or a grader.
3. BenchmarkRun: run a TaskSet across selected models and record measurements (quality via exact or JSON scoring first, cost, latency, reliability, JSON and tool success).
4. Scorecard: per-model, per-task local results, stored and inspectable.
5. RoutingPolicy v1: hard filters (context window, JSON, tools, privacy or local-only) plus a scoring step that consumes scorecards, plus a fallback chain.
6. RoutingDecision explanation: every route states why the chosen model won and what the fallbacks were.
7. Slim default install: base routing works without heavy ML dependencies.

## What makes the MVP impressive

* It answers a real question developers actually have ("which model for this task") with their own data, not marketing.
* It runs locally and privately. The scorecards never leave the machine.
* It explains its routing decisions instead of being a black box.
* It treats local models as first-class sources, not an afterthought.

## Out of scope for V2 MVP

* Hosted or multi-user deployment.
* A web dashboard or API server.
* Provider-count expansion for its own sake.
* Telemetry or analytics collection.
* OAuth flows (API key and PAT auth is sufficient for MVP).
* Postgres or any non-SQLite store.

## Delayed (after MVP)

* LLM-as-judge scoring beyond the minimum needed; start with exact and JSON or schema scoring.
* A lighter semantic cache (`semantic-cache-v2`) is future work and not on the MVP critical path. No semantic cache is currently implemented (the exact SQLite cache is the only cache), and there is no heavy-cache install path. Redis is a future option only if a daemon, team, or shared-cache mode is added.
* TUI V2 polish and motion; a functional workbench layout is enough for MVP, polish follows.
* Safe agent mode promotion; gated behind the P0 agent-safety work and not required for the routing and benchmarking thesis.

## Phase order

The MVP is delivered across the branches in `docs/roadmap/BRANCH_ROADMAP.md`. The ordering that matters: slim dependencies and stabilize the cache first, fix agent safety and registry integrity, clean the config seam, then build ModelSource, then sources, then the policy engine, then benchmarks and scorecards. TUI V2, semantic cache v2, and safe agent mode come after the core loop works.

## Definition of done for the MVP as a whole

* A developer can go from zero to a routed prompt that was chosen using their own benchmark scorecards, with an explanation, using at least one local and one cloud source.
* Base install does not require `torch`, `sentence-transformers`, or `qdrant-client`.
* No documented feature is unimplemented, and no implemented behavior is undocumented.
