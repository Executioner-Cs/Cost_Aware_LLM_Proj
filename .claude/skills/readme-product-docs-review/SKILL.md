---
name: readme-product-docs-review
description: Review README and docs for Orchestrator CLI so positioning is honest and on-product. Enforces no fake features, accurate install commands, a clear current-vs-planned split, no generic gateway claims, no unsafe agent claims, and a visible roadmap.
---

# readme-product-docs-review

## When to use

* Any change to `README.md` or files under `docs/`.
* When command examples, install instructions, or feature claims change.
* As the docs gate before a docs branch merges.

## Goal

Documentation that positions the product correctly and tells the truth about what is built versus planned, with install and usage instructions that actually work.

## Non-goals

* Not code correctness (use post-change-review).
* Not prose-style polish for its own sake (slop-hunter covers AI-slop and drift).
* Does not invent or approve features; it checks that docs match reality.

## Inputs required

* The doc diff under review.
* Ground truth: `pyproject.toml` (deps and scripts), the actual CLI command surface in `cli/`, `core/cache.py` (cache reality), `agent/` (security reality).
* `docs/product/PRODUCT_DIRECTION.md` and the "Product identity (V2)" section of `.claude/CLAUDE.md`.

## Review steps

1. Verify every feature claim against source. If the code does not do it, the doc must not say it does.
2. Verify install commands run as written and do not reference extras that do not exist in `pyproject.toml`.
3. Verify the current-vs-planned split is explicit: planned items are labeled, implemented items are accurate.
4. Verify positioning: local-first benchmark-driven workbench, not a gateway, router-only, or coding agent.
5. Verify security claims: no claim of network isolation or OS-level sandbox that source does not enforce; agent mode marked experimental.
6. Verify cache claims: exact default, semantic optional, correctness language present.
7. Verify the roadmap is visible and matches `docs/roadmap/BRANCH_ROADMAP.md`.
8. Verify command examples use real command names (cross-check `cli/`).

## Red flags

* A feature described as working that the code does not implement.
* An install command referencing a non-existent extra.
* Planned commands shown as if implemented, or without a "planned" label.
* Generic gateway or provider-count framing.
* Network isolation or safe-sandbox claims not backed by source.
* The semantic cache or agent mode sold as the headline.

## Output format

```
Scope: <doc files>
Feature-claim accuracy: <each claim: verified | false (evidence)>
Install accuracy: <commands run as written? extras real?>
Current-vs-planned: <clear | mixed>
Positioning: on-product | drifting
Security claims: <accurate | overclaim>
Cache claims: <accurate | overclaim>
Roadmap visible and consistent: yes/no
Verdict: keep | fix | reject
Required reviewers: docs-product-positioning-reviewer, product-strategy-reviewer, slop-hunter
```

## Stop conditions

* Reject any doc that claims an unimplemented feature is implemented.
* Reject any install command that does not work as written.
* Reject any unsafe security claim (network isolation, OS sandbox) not enforced in source.
* Do not edit source from this skill; docs only, and only after the review is acted on.

## Example invocation

"Run readme-product-docs-review on the README rewrite before we merge the docs branch."
