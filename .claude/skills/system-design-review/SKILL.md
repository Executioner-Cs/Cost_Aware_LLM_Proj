---
name: system-design-review
description: Focused system design review for an Orchestrator CLI feature, module, bug fix, or architecture decision covering maintainability, scalability, latency, security, boundaries, contracts, cache correctness, reliability, and testing, with a tactical vs strategic call.
---

# system-design-review

## Purpose

Focused system design review for a feature, module, bug fix, or architecture decision. Evaluate the shape of the design before or during implementation and recommend whether to act tactically now or strategically later.

## When to use

* Designing or changing a feature, module, or provider/cache boundary.
* Provider integration changes and semantic cache/embeddings changes (per the routing matrix).
* Any architecture decision (new store, new provider, new agent capability).

## Required pre-read

* `.claude/CLAUDE.md` (architecture expectations, invariants).
* The relevant module(s) and their contracts in `schemas/` and `providers/base.py`.
* Existing tests for the area.

## Required agents

* principal-system-architect for boundaries and tradeoffs.
* Domain agents for the area under design (provider-integration-reviewer, embeddings-retrieval-reviewer, database-persistence-reviewer, api-contract-architect, security-architect, agent-runtime-architect).
* qa-sdet-lead for testing strategy.

## Process

Assess the design against each dimension and cite evidence:

1. Maintainability: does it fit the `cli -> services -> core -> providers/db/embeddings` direction; does it avoid deepening `core -> services` coupling.
2. Scalability: behavior as model count, accounts, and cache size grow.
3. Latency: embedding cost, Qdrant lookup, provider call time, any added round trips.
4. Security: secrets, sandbox, trust boundaries for tool and provider output.
5. Provider boundaries: are external APIs isolated behind connectors/adapters and shared contracts.
6. Database boundaries: persistence ownership, no-migration risk, dual-store consistency.
7. Schema contracts: explicit request/response and tool contracts; mismatch risk.
8. Semantic cache correctness: hit criteria and threshold/TTL implications.
9. Operational reliability: failure modes, fallbacks, error visibility (no silent swallowing).
10. Testing strategy: what proves the design works; what is currently untested.
11. Product fit (V2): does the design advance the local-first benchmark-driven workbench, or does it drift toward a generic gateway, a provider-count chase, or a coding agent. For ModelSource designs, confirm sources, not API keys, are the identity and existing providers are wrapped behavior-preservingly. For routing-policy designs, confirm cheapest-capable (not cheapest-overall), a quality floor, privacy/local and context/tool/JSON hard filters, and that decisions are explained. For benchmark designs, confirm exact and JSON scoring before LLM-as-judge, visible sample size, and that scorecards feed routing. Pull in the matching V2 architect agent (model-source-architect, routing-policy-architect, benchmark-evals-architect, business-logic-reviewer) per the V2 routing matrix in `.claude/CLAUDE.md`.
12. Tactical vs strategic recommendation.

## Output format

```
Design under review: <short>
Dimension findings:
  Maintainability / Scalability / Latency / Security / Provider boundaries /
  Database boundaries / Schema contracts / Semantic cache / Reliability / Testing
  - <each with evidence and risk>
Recommendation: tactical (do now) | strategic (plan later) | both with split
Required follow-up reviewers: <list>
Open questions for the user: <list>
```

## Stop conditions

* Stop and surface to the user when the design changes a hard invariant (sandbox confinement, cache hit criteria, secret handling, DB schema without migrations).
* Do not approve a design whose failure modes are silent or untested; require visibility and a test plan first.
* Do not edit code from this skill. Design review only.
