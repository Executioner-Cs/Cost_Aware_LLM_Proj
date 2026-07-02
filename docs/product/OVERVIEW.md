# Orchestrator CLI: Overview

Orchestrator CLI is a local-first AI routing, benchmarking, and execution workbench for developers. It runs on your machine and keeps your data local.

## What it does

You connect model sources (cloud providers and local or OpenAI-compatible endpoints), optionally benchmark models on your own tasks, and route each prompt to a model chosen by cost and capability (and, opt-in, by your benchmark scorecards), with an explanation of the choice.

## Implemented today

* Routing across Anthropic, OpenAI, Groq, and Gemini, plus local Ollama and OpenAI-compatible HTTP endpoints, behind one model-source abstraction. The router picks the cheapest model that satisfies the task's tier and capability constraints.
* Dynamic model discovery on connect, with Fernet-encrypted credential storage in SQLite.
* Benchmarks and scorecards: define task sets and score models locally with deterministic grading (exact, contains, json_valid). No LLM-as-judge.
* A routing policy engine with named policies, hard filters, a scoring formula, a fallback chain, and a per-decision explanation. Scorecard-aware routing is opt-in (the `benchmarked` policy); the default route stays cost-and-capability based.
* An exact-match SQLite cache by default that pulls no ML or vector dependencies, with TTL on read.
* Traces for every route (tokens, USD cost, latency, cache hit or miss).
* A Typer CLI and a Textual TUI that run the same workflows.
* A slim base install; provider SDKs and the TUI are optional extras loaded lazily.

## Honest limitations

* Cloud providers are Anthropic, OpenAI, Groq, and Gemini; local sources are Ollama and OpenAI-compatible endpoints. No hosted-gateway or custom-plugin sources yet.
* Benchmark grading is deterministic only.
* Model identity is `(provider, external_model_id)`, so two local endpoints exposing the same model name can collide in the registry.
* No hard budget enforcement (cost is reported and warned, not capped).
* The agent runtime is experimental and not certified production-safe (see the README security section).

## Planned (broad terms)

* A lighter, optional semantic cache to complement the exact cache (the heavy legacy semantic cache was removed and is not coming back).
* Source-qualified model identity so same-named models across endpoints do not collide.
* Latency and reliability as live routing dimensions once benchmarks record them.

See `CHANGELOG.md` for what shipped in each release and `README.md` for usage.
