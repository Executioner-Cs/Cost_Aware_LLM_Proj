# ADR-001: Local-First Benchmark-Driven Routing Workbench

Status: accepted

Date: 2026-06-29

## Context

Orchestrator CLI began as a cost-aware multi-provider router with a semantic cache. In that framing it competes directly with established AI gateways and routers (for example LiteLLM and OpenRouter) and with cost-tracking tools. Against those, it is a weaker version of products that already exist: it has fewer providers, less operational maturity, and no hosted convenience. Cheapest-model routing is a commodity. Provider count is not a moat. The semantic cache is a feature, not a reason to switch tools.

At the same time, developers have a real and growing problem that none of those tools solve well: deciding which model to use for which task. Public leaderboards measure generic benchmarks, not the developer's tasks. Provider marketing is not neutral. The honest answer requires measuring candidate models on the developer's own representative tasks, accounting for quality, cost, latency, privacy, and tool or JSON requirements. The rise of capable local models makes this sharper, because privacy and local-only constraints are now first-class concerns.

## Decision

Reposition Orchestrator CLI as a local-first AI routing, benchmarking, and execution workbench for developers. Routing is driven by local, task-specific scorecards produced by benchmarking models on the developer's own TaskSets. The model unit becomes ModelSource (local, cloud, OpenAI-compatible gateway, custom) rather than provider plus API key. Routing becomes policy-based (hard filters plus scoring plus fallback) and explainable, rather than cheapest-overall.

Concretely:

* Keep everything local-first. No required hosted services, no telemetry by default.
* Keep the default route path slim. The heavy ML and vector dependencies of the legacy semantic cache were removed; any future cache backend stays optional.
* Treat benchmark-driven routing and local scorecards as the differentiator.
* The legacy heavy semantic cache (sentence-transformers + Qdrant) was removed; the exact SQLite cache is the current implemented cache. A lighter `semantic-cache-v2` remains a future optional alternative. Redis is not part of this decision; local-first with no required daemon stays the default.
* Treat agent mode as experimental until its P0 safety work lands.

## Alternatives considered

1. Stay a cost-aware gateway or router. Rejected: directly competes with stronger incumbents on their terms (provider breadth, hosting, maturity), where this project loses.
2. Become a hosted dashboard or SaaS. Rejected: abandons the local-first, privacy advantage and adds operational burden that does not serve the core thesis.
3. Lead with the semantic cache as the product. Rejected: caching is a commodity optimization, it does not answer the developer's real question, and presenting it as central conflicts with making the default path slim.
4. Become a general coding agent. Rejected: a crowded, capital-intensive space, and orthogonal to the routing and benchmarking thesis. Agent mode stays a supporting, gated capability.

## Consequences

Positive:

* A defensible niche. Local scorecards built from the user's own tasks are data no hosted competitor has and no leaderboard provides.
* Privacy as a feature, not a limitation. Measurements and tasks stay on the machine.
* A clear product narrative that orders the roadmap: sources, then policy, then benchmarks, then experience.

Costs and risks:

* More to build than a router. The benchmark and scorecard loop is the hard part and must actually work to deliver the thesis.
* Requires discipline to not drift back into provider-count or gateway framing.
* Local model support and an honest agent-safety story are now prerequisites, not nice-to-haves.

## Why a generic gateway or router loses here

It competes on breadth, hosting, and maturity, where incumbents are ahead. It cannot answer "is this model good enough for my task" because it has never measured the user's tasks. Its switching cost for users is low and its moat is thin.

## Why local-first benchmark-driven routing wins

It answers the developer's actual question with the developer's own data, privately, and explains its routing decisions. The scorecards are a private, task-relevant asset that compounds in value as the developer adds tasks and models. The moat is grounded measurement, not breadth, and it is hard to replicate without the user's local data.
