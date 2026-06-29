# Product Direction

Status: accepted direction for V2. This document is the source of truth for what Orchestrator CLI is and is not. README, TUI copy, and help text must agree with it.

## Old positioning (deprecated)

> "Connect provider API keys and route prompts to the cheapest model."

This framing made the project a weaker version of tools that already exist (AI gateways, routers, cost trackers). Cheapest-model routing is a commodity. Provider breadth is not a moat. The semantic cache, while real, is not a reason to choose this tool over an established gateway.

## New product identity

Orchestrator CLI is a local-first AI routing, benchmarking, and execution workbench for developers.

One-line promise:

> Benchmark local and cloud models on your own tasks, then route every prompt to the model that actually earned it, based on quality, cost, latency, privacy, reliability, context, JSON support, tool support, and safety.

## Target user

A developer who already has access to several models (cloud API keys, and increasingly local models) and is guessing which one to use for which task. They do not trust provider marketing or public leaderboards to answer that question for their work, because the right model depends on their own tasks, budget, privacy needs, latency tolerance, and tool or JSON requirements.

## Why it exists

Model choice is currently a guess. Leaderboards measure generic benchmarks, not your tasks. Provider marketing optimizes for the provider. The only honest answer to "which model should I use" is: run a representative set of your own tasks across candidate models, measure quality, cost, latency, and reliability locally, and let those measurements drive routing. Orchestrator CLI is the tool that makes that loop cheap and repeatable on a developer's own machine.

## Core workflows

1. Register model sources (today: cloud providers; planned: local and OpenAI-compatible sources).
2. Define a TaskSet of representative tasks (planned).
3. Run a BenchmarkRun across candidate models and produce local Scorecards (planned).
4. Route prompts through a RoutingPolicy that uses those scorecards plus hard filters (planned policy engine; basic cost-and-capability routing exists today).
5. Inspect traces and route explanations to understand why a model was chosen.

## What this is

* A local-first routing and benchmarking workbench.
* A developer command-line and terminal tool.
* A producer of local, task-specific scorecards.
* A model source registry (planned abstraction over today's provider plus account model).
* A policy-based router that explains its decisions.
* A trace and explanation surface.

## What this is not

* Not a generic AI gateway.
* Not a LiteLLM or OpenRouter clone.
* Not a hosted dashboard or SaaS.
* Not a provider-count race.
* Not a general coding agent.
* Not just cheapest-model routing.

## Current capabilities vs planned

Current, implemented today:

* Routing across Anthropic, OpenAI, Groq, Gemini, picking the cheapest model that satisfies the task's tier and capability constraints.
* Dynamic model discovery on connect, with encrypted credential storage.
* A Typer CLI and a Textual TUI that share the same workflows.
* Traces with token counts, USD cost, latency, and cache hit or miss.
* Exact-match SQLite cache by default (no ML dependencies). The legacy heavy semantic cache was removed; a lighter one is planned.
* An experimental ReAct agent runtime (see caveat below).

Planned, not yet built:

* ModelSource abstraction and local or OpenAI-compatible sources (Ollama and similar).
* TaskSet, BenchmarkRun, Scorecard, and the benchmark-driven routing loop.
* RoutingPolicy engine with hard filters, scoring, fallback chains, and route explanations.
* TUI V2 organized around sources, benchmarks, scorecards, routing, and traces.
* Lightweight install profiles (optional extras) so heavy dependencies are not required for base routing.

## Why benchmark-driven routing is the differentiator

A gateway can route. A router can pick the cheapest model. Neither answers "is this model actually good enough for my task," because neither has measured your tasks. Local scorecards built from the user's own TaskSets are data that no hosted competitor has and no leaderboard provides. Routing that is driven by those scorecards is defensible precisely because it is local and task-specific. That is the moat: not breadth, but grounded, private, task-relevant measurement.

## Agent mode caveat

Agent mode is experimental. The sandbox is path-confinement only, not OS-level isolation, and `network_disabled` is a config flag that is not enforced in source. Do not run agent mode against repositories that contain real credentials until the P0 agent-safety branch lands. Do not promote agent mode as a headline feature before then.

## Cache caveat

The default and only implemented cache is exact-match and pulls no embedding or vector dependencies. The legacy heavy semantic cache (local embeddings plus Qdrant) was removed because it was too heavy for the base product and was not the differentiator; `cache.mode = "semantic"` now returns a clear error directing the user to exact mode. A lighter semantic cache is planned as future work (semantic-cache-v2, using a lighter approach such as sqlite-vec, provider embeddings, or FastEmbed). Cache correctness beats hit rate: a cache must never serve a different question's answer. Do not market the cache as the product.
