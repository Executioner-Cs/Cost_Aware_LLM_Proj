---
name: model-source-design
description: Guide the transition from provider plus account to a ModelSource abstraction in Orchestrator CLI. Enforces sources (local, cloud, gateway, custom) as the identity, existing providers wrapped behavior-preservingly, and no provider-count chase.
---

# model-source-design

## When to use

* Designing or reviewing the `architecture/model-source-abstraction` branch.
* Adding a new source type (`sources/openai-compatible-and-ollama`).
* Any change to how models are registered, identified, or grouped.

## Goal

Introduce ModelSource as the unit of the system: a registered source of models (local, cloud, OpenAI-compatible gateway, custom). Existing providers become one source type, wrapped without changing current routing behavior.

## Non-goals

* Not routing policy or scoring (use routing-policy-design).
* Not benchmark design (use benchmark-scorecard-design).
* Not a push to maximize the number of providers.

## Inputs required

* `providers/base.py` (connector and adapter ABCs, `ModelInfo`) and the four provider implementations.
* `db/models.py` (`connected_accounts`, `model_registry`) and `schemas/`.
* The "Strategic direction" section of `.claude/CLAUDE.md` and `docs/architecture/ORCHESTRATOR_V2_ARCHITECTURE.md`.

## Review steps

1. Confirm the abstraction's identity is the source, not a raw API key. A key is one auth detail of a cloud source, not the unit.
2. Confirm existing providers map onto the abstraction as one source type with no behavior change to current routing.
3. Confirm the abstraction supports local, cloud, gateway, and custom source types without special-casing each provider.
4. Confirm source attributes that routing will need are modeled: locality and privacy (local-only), auth method, capability and pricing, availability.
5. Confirm the design does not encourage adding sources for breadth alone; each source type must earn its place against the product thesis.
6. Confirm the DB and schema changes have a migration story or an explicit accepted-risk note (no migration system exists).

## Red flags

* The API key, not the source, treated as the primary entity.
* A new source that breaks or subtly changes existing provider routing.
* Per-provider special cases leaking into core instead of living behind the abstraction.
* Privacy or local-only modeled as an afterthought rather than a first-class attribute.
* A provider-count expansion justified by breadth rather than user value.

## Output format

```
Scope: <files>
Identity check: source-as-unit confirmed? yes/no
Behavior preservation: existing routing unchanged? evidence
Source-type coverage: local | cloud | gateway | custom, supported cleanly?
Attribute modeling: privacy/local, auth, capability, pricing, availability, present?
Schema/migration note: <story or accepted-risk>
Verdict: keep | fix | reject
Required reviewers: model-source-architect, provider-integration-reviewer, api-contract-architect, database-persistence-reviewer
```

## Stop conditions

* Reject if existing provider routing behavior would change without explicit intent and tests.
* Reject if a schema change has no migration story or accepted-risk note.
* Stop and reframe if the design is really a provider-count expansion.
* Do not edit code from this skill.

## Example invocation

"Apply model-source-design to the ModelSource ABC proposal before we build it."
