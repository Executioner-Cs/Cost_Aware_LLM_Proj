# Orchestrator CLI

> Benchmark local and cloud models on your own tasks, then route every prompt to the model that actually earned it, based on quality, cost, latency, privacy, reliability, and capability.

Orchestrator CLI is a local-first AI routing and benchmarking workbench for developers. It runs on your machine, keeps your data local, and is built to answer one question that leaderboards and provider marketing cannot answer for you: which model should I actually use for this task.

This README separates what works today from what is planned. Planned items are labeled. Nothing here describes a feature that does not exist.

## Table of Contents

1. [What this is](#what-this-is)
2. [What this is not](#what-this-is-not)
3. [Why it exists](#why-it-exists)
4. [Core concepts](#core-concepts)
5. [Current capabilities](#current-capabilities)
6. [Installation](#installation)
7. [First-time setup](#first-time-setup)
8. [Usage](#usage)
9. [Cache status](#cache-status)
10. [Security status](#security-status)
11. [Future direction (V2 roadmap)](#future-direction-v2-roadmap)
12. [Development](#development)

---

## What this is

* A local-first AI routing and benchmarking workbench.
* A developer command-line and terminal tool (`orchestrator`).
* A producer of local, task-specific scorecards (implemented: `orchestrator benchmark`).
* A model source registry: cloud providers, local Ollama, and OpenAI-compatible endpoints behind one source abstraction.
* A policy-based router that explains its decisions (named policies with scoring and a fallback chain, including opt-in scorecard-aware routing).
* A trace and explanation surface for every route.

## What this is not

* Not a generic AI gateway.
* Not a LiteLLM or OpenRouter clone.
* Not a hosted dashboard or SaaS.
* Not a provider-count race.
* Not a general coding agent.
* Not just cheapest-model routing.

## Why it exists

Developers are guessing which model to use. Public leaderboards measure generic benchmarks, not your tasks. Provider marketing is not neutral. The right model depends on your actual tasks, your budget, your privacy needs, your latency tolerance, and whether you need reliable JSON or tool calls.

The honest way to choose is to run a representative set of your own tasks across candidate models, measure the results locally, and let those measurements drive routing. Orchestrator CLI exists to make that loop cheap, private, and repeatable on your own machine. See [docs/product/PRODUCT_DIRECTION.md](docs/product/PRODUCT_DIRECTION.md) for the full positioning.

## Core concepts

These are the domain concepts the product is organized around. Concepts marked planned are not yet implemented; they define the direction (see [docs/architecture/ORCHESTRATOR_V2_ARCHITECTURE.md](docs/architecture/ORCHESTRATOR_V2_ARCHITECTURE.md)).

* Model Sources: a registered source of models, local, cloud, OpenAI-compatible, or custom. The abstraction exists today and cloud providers, Ollama, and OpenAI-compatible endpoints are supported. Source-as-primary-identity (replacing provider plus account) is still planned.
* Task Sets: your representative tasks with expected outputs and a deterministic grader (`orchestrator benchmark create` / `add-task`).
* Benchmark Runs: an execution of a Task Set across selected models, producing measurements (`orchestrator benchmark run`).
* Scorecards: per-model local results (pass rate, average latency and cost) that can feed routing (`orchestrator benchmark scorecards`). Grading is deterministic only (exact / contains / json_valid); no LLM-as-judge.
* Routing Policies: hard filters plus a scoring formula plus a fallback chain (`default`/`cheapest`, `privacy-first`, `quality-first`, `benchmarked`).
* Routing Decisions: the chosen model plus the reasons it was chosen. Explicit policies emit a human-readable explanation; the default route is unchanged.
* Fallback Plans: the ordered alternatives if the primary model is filtered out, carried on each routing decision.
* Execution Traces: a record of each route. Today traces are flat rows with cost, tokens, latency, and cache status; richer execution traces are planned.

## Current capabilities

Implemented and working today:

* Multi-provider routing across Anthropic, OpenAI, Groq, and Gemini. The router picks the cheapest model that satisfies the task's tier and capability constraints (not the cheapest model overall).
* Dynamic model discovery: on `connect`, the provider's models API is queried for the models your key can access, rather than a hardcoded list.
* Local and OpenAI-compatible sources: connect Ollama (`orchestrator connect ollama --base-url http://localhost:11434`) or any OpenAI-compatible endpoint (`orchestrator connect openai-compatible --base-url <url> --api-key <key>`); their models join the same routing pool over httpx, with no extra dependencies.
* Benchmarks and scorecards: define your own task sets and score models on them locally (`orchestrator benchmark create | add-task | run | scorecards`). Deterministic grading only (exact / contains / json_valid); results persist to local SQLite.
* Routing policy engine: named policies with hard filters, a scoring formula, and a fallback chain, with a human-readable explanation per decision. Opt-in scorecard-aware routing (`route --policy benchmarked [--task-set S]`) prefers models that earned it on your tasks, falling back to cheapest when a model has no scorecard. The default route is unchanged.
* Encrypted credentials: API keys are Fernet-encrypted before they are written to SQLite.
* A Typer CLI and a full-screen Textual TUI that run the same workflows, including the benchmark and policy commands.
* Traces: every route records token counts, USD cost, latency, and cache hit or miss.
* Slim default install: base routing, the exact-match cache, persistence, and the CLI pull no ML, vector, provider-SDK, or TUI packages; those are optional extras loaded lazily. See [Installation](#installation).
* Exact-match SQLite cache by default (no ML dependencies). The legacy semantic cache was removed; a lighter one is planned. See [Cache status](#cache-status).
* An experimental tool-using agent runtime. See [Security status](#security-status) before using it.

Current limitations:

* Sources: four cloud providers (Anthropic, OpenAI, Groq, Gemini), plus local Ollama and OpenAI-compatible HTTP endpoints. No hosted-gateway or custom-plugin sources yet.
* Benchmark grading is deterministic only (exact / contains / json_valid); there is no LLM-as-judge.
* Scorecard-aware routing is opt-in (the `benchmarked` policy); the default route remains cost-and-capability based.
* Model identity is `(provider, external_model_id)`, so two local endpoints exposing the same model name can collide in the registry (one endpoint per local provider is supported today).
* No hard budget enforcement (cost is reported and warned, not capped).

## Installation

Requirements: Python 3.11 or newer, and a terminal that supports 256-color ANSI.

```bash
git clone https://github.com/Executioner-Cs/Cost_Aware_LLM_Proj.git
cd Cost_Aware_LLM_Proj

python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# Base install: routing, the exact-match cache, persistence, and the CLI.
# Pulls no ML, vector, provider-SDK, or TUI packages.
pip install -e .
```

The base install is intentionally light. The default route path uses the exact-match cache and imports no machine-learning or vector libraries. Install only the extras you need:

| Extra | Adds | Needed for |
|-------|------|------------|
| `openai` | openai SDK | routing to OpenAI models |
| `anthropic` | anthropic SDK | routing to Anthropic models |
| `gemini` | google-genai SDK | routing to Gemini models |
| `providers` | all three provider SDKs | routing to any cloud provider |
| `tui` | textual, questionary | the immersive TUI and the interactive provider picker |
| `all` | everything above | a full-featured install |

```bash
pip install -e ".[providers]"        # cloud routing
pip install -e ".[providers,tui]"    # cloud routing plus the TUI
pip install -e ".[all]"              # everything optional
```

Provider SDKs and the TUI load lazily, so a base install runs the CLI fine and a missing extra produces a clear message naming the one to install. groq routing reuses the openai SDK, so it needs the `openai` extra (there is no separate groq extra).

## First-time setup

```bash
orchestrator init
```

This creates `~/.orchestrator/` with a config file and a SQLite database. On an interactive terminal it offers a provider picker and then launches the TUI. On a non-interactive terminal it prints the manual next steps.

Connect at least one provider:

```bash
orchestrator connect openai
orchestrator connect anthropic
orchestrator connect groq
orchestrator connect gemini
```

Keys are also picked up from environment variables or a `.env` file (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`). `connect` validates the key, discovers available models, and stores the encrypted key in SQLite. Only connected providers participate in routing.

## Usage

### Routing a prompt (today)

```bash
orchestrator route "Summarize this meeting note"
orchestrator route "Extract line items as JSON: ..." --task json_extract
orchestrator route "Reason through this tradeoff" --quality best
orchestrator route "What would this cost?" --dry-run
```

Flags: `--task` (`simple`, `json_extract`, `reasoning`, `vision`, `tools`; auto-detected if omitted), `--quality` (`cheap`, `balanced`, `best`; default `balanced`), `--dry-run` (estimate cost without calling a provider).

### Inspecting the system

```bash
orchestrator model list                 # registry with pricing and capability flags
orchestrator accounts list              # connected accounts
orchestrator accounts sync <id>         # re-validate key and refresh models
orchestrator accounts disconnect <id>   # remove an account (partial ID prefix works)
orchestrator trace list                 # recent routes with cost and latency
orchestrator trace show <id>            # one trace in detail
orchestrator cache stats                # cache overview
orchestrator shell                      # launch the full-screen TUI
```

### The TUI

Run `orchestrator` with no arguments on an interactive terminal, or `orchestrator shell`. It is a full-screen Textual app with a status bar (provider count, cache state, quality mode, session cost), an output panel, a recent-activity panel, and a command input. The same commands work inside the TUI without the `orchestrator` prefix. The TUI shows real data, not placeholders.

### Benchmarks and policy routing

```bash
# Define a task set and add graded tasks
orchestrator benchmark create my-tasks
orchestrator benchmark add-task my-tasks "2+2?" --expected 4 --grader exact
orchestrator benchmark add-task my-tasks "Capital of France?" --expected paris --grader contains

# Run it across selected models (or all enabled) and view scorecards
orchestrator benchmark run my-tasks --models gpt-4o-mini,llama3
orchestrator benchmark scorecards --task-set my-tasks

# Route under a named policy; the benchmarked policy uses your scorecards
orchestrator route "..." --policy privacy-first
orchestrator route "..." --policy benchmarked --task-set my-tasks
```

Grading is deterministic (`exact`, `contains`, `json_valid`); `contains`/`exact` require `--expected`. The `benchmarked` policy prefers the highest-scoring capable model and falls back to cheapest when a model has no scorecard. See [docs/roadmap/BRANCH_ROADMAP.md](docs/roadmap/BRANCH_ROADMAP.md) for what is still planned.

## Cache status

The cache is selected in `core/cache.py`:

* The only implemented cache is an exact-match SQLite cache (the default). The key is a hash of the normalized prompt plus task type plus quality. It imports no embedding model and no vector store. An exact hit can only ever return the same question's answer at the same task and quality, so it cannot serve a different prompt's answer. TTL is enforced on read.
* `cache.mode = "off"` disables the cache.
* `cache.mode = "semantic"` is no longer available. The legacy heavy semantic cache (local embeddings plus an embedded Qdrant store) was removed because it was too heavy for the base product and was not the differentiator. Setting it now returns a clear error directing you to exact mode.

Current vs planned:

* Exact cache as the default: implemented.
* Legacy semantic cache v1: removed, along with its `sentence-transformers` and `qdrant-client` dependencies.
* A lighter semantic cache: planned as future work (`semantic-cache-v2`), using a lighter approach such as sqlite-vec, provider embeddings, or FastEmbed. Not implemented.

Cache correctness matters more than cache cleverness. A cache must never serve a different question's answer.

## Security status

Agent mode is experimental. It has had P0 safety hardening, but it is not certified production-safe. Read this before running it.

P0 hardening that has landed:

* Tool subprocesses run with a scrubbed environment: no provider API keys, no `ORCHESTRATOR_KEY_FILE`, and nothing matching `*_API_KEY` / `*_TOKEN` / `*_SECRET` / `*_PASSWORD` / `*_CREDENTIAL*`.
* `run_python` is disabled by default and is not even offered to the model unless `[agent] allow_python = true`.
* `run_shell` is disabled by default (`allow_shell = false`), gated by a blocked-pattern list, and only offered to the model when enabled.
* Tool-call logs are redacted: secret-looking keys, values, and `NAME=value` assignments become `***REDACTED***` before they are stored.
* File tools deny access to sensitive paths (`.env`, `*.key`, `*.pem`, `orchestrator.db`, `.orchestrator/`, credential files), and `write_file` refuses to overwrite an existing file unless `overwrite=true`.

Known limitations (still true):

* The sandbox is path-confinement only (paths resolved under a sandbox root). It is not OS-level isolation.
* `network_disabled` is advisory only. It is not enforced in source; do not assume network isolation.
* Enabling `allow_python` or `allow_shell` is arbitrary code execution under your user account. Enable it only in a trusted environment, and avoid pointing the sandbox root at a tree containing sensitive data.

API keys are encrypted at rest with Fernet and are never printed. Treat tool outputs, file contents, and provider responses as untrusted input.

## Future direction (V2 roadmap)

The product is moving from a cost-aware router to a benchmark-driven routing workbench. Work is sequenced one concern per branch. As of 0.2, items 6 through 10 (Model Sources, local/OpenAI-compatible sources, the policy engine, benchmarks and scorecards, and the TUI workbench), the P0 agent-safety hardening (item 2), and scorecard-aware routing have landed; see [CHANGELOG.md](CHANGELOG.md). Item 11 (`semantic-cache-v2`) is deferred. Summary order (full detail in [docs/roadmap/BRANCH_ROADMAP.md](docs/roadmap/BRANCH_ROADMAP.md)):

1. `refactor/slim-deps-and-cache-tiers`: slim default dependencies; exact cache default; semantic optional. (Cache tier code and the optional-dependency extras have landed.)
2. `security/p0-agent-safety`: fix P0 agent-runtime security before any promotion of agent mode.
3. `docs/v2-product-direction`: docs and Claude support system aligned to V2.
4. `fix/model-registry-integrity`: registry correctness and integrity.
5. `refactor/config-routing-seam`: clean the router-to-config coupling.
6. `architecture/model-source-abstraction`: introduce Model Sources, wrap existing providers.
7. `sources/openai-compatible-and-ollama`: add local and OpenAI-compatible sources.
8. `routing/policy-engine-v1`: hard filters, scoring, policies, fallback chains, explanations.
9. `evals/benchmark-scorecards-v1`: Task Sets, Benchmark Runs, scoring, Scorecards that feed routing.
10. `design/tui-v2-workbench-experience`: TUI around sources, benchmarks, scorecards, routing, traces.
11. `cache/semantic-cache-v2`: a lighter semantic cache to replace the removed v1 (candidates: sqlite-vec, provider embeddings, FastEmbed). Not implemented.
12. `agent/safe-agent-mode`: re-enable and promote agent mode only after P0 is fixed.

## Development

```bash
# Install the test tools plus every optional extra, so the full suite
# (provider adapters, TUI) can import what it exercises.
pip install -e ".[all,dev]"
pytest
```

`[dev]` alone installs only the test tools (`pytest`, `pytest-asyncio`, `pytest-mock`); combine it with `[all]` to run the whole suite. The test suite covers the task classifier, cost estimator, model selector, exact cache, router integration (with mocked providers), provider adapters, connect flows, optional-dependency packaging, and an end-to-end CLI simulation under `tests/tests_e2e_cli_simulation/`. There is no lint, format, or typecheck command in this repo.

Architecture, product direction, and the branch roadmap live under [docs/](docs/). The operating guide for Claude Code in this repo is at [.claude/CLAUDE.md](.claude/CLAUDE.md).
