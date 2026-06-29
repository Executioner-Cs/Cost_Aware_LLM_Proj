---
name: post-change-review
description: Review the git diff after an Orchestrator CLI change across behavior, QA, readability, security, provider contracts, persistence, and cache correctness, then return a keep/rewrite/revert verdict.
---

# post-change-review

## Purpose

Review changed files or the git diff after code changes. This is the gate that runs after non-trivial edits, before the change is considered done.

## When to use

* After any non-trivial diff.
* Always after high-risk changes, regardless of size.
* Before reporting a task complete.

## Required pre-read

* `git diff` (and `git status`) for the change under review.
* `.claude/CLAUDE.md` (invariants and high-risk areas).
* The tests covering the changed code.

## Required agents

* behavior-preservation-checker (always).
* qa-sdet-lead (always for logic changes).
* refactoring-readability-reviewer or slop-hunter (readability/maintainability).
* Domain agents for whatever the diff touches (security-architect, agent-runtime-architect, provider-integration-reviewer, embeddings-retrieval-reviewer, database-persistence-reviewer, cli-interface-reviewer, api-contract-architect, python-packaging-reviewer).

## Process

Inspect the diff against each dimension and record findings with `file:symbol` evidence:

1. Behavior preservation: did routing, cache hit/miss, provider behavior, CLI output/exit codes, DB writes, or agent runtime behavior change unintentionally?
2. QA and regression: new edge cases, broken paths, missing or stale tests.
3. Readability: naming, control flow, function size, hidden behavior in cleanup.
4. Security: secret exposure, key handling, sandbox confinement, command/prompt logging, trust of tool outputs.
5. Provider contracts: shared response normalization, tool-call mapping consistency across providers.
6. Database/persistence: schema impact (no migrations exist), transactions, dual-store consistency, cascade deletes.
7. Cache correctness (tiered): exact cache as default and its TTL-on-read; semantic hit criteria (similarity + task_type + quality), thresholds, semantic TTL gap, wrong-answer reuse risk; that heavy imports stay lazy and off the default path.
8. Product positioning (docs and user-facing copy): does the change keep the local-first benchmark-driven framing, avoid generic gateway or router claims, mark planned features as planned, and avoid promoting agent mode or the semantic cache as headline. Apply `product-direction-guard` on any docs or copy change.
9. Release readiness (when reviewing a branch for merge): tests run or explicitly skipped with reason, docs updated if behavior changed, no source drift, no accidental dependency or schema change. Apply `release-readiness-review`.

## Output format

```
Diff scope: <files>
Findings by dimension:
  Behavior: <findings or none>
  QA: <findings or none>
  Readability: <findings or none>
  Security: <findings or none>
  Provider contracts: <findings or none>
  Database/persistence: <findings or none>
  Cache (tiered): <findings or none>
  Product positioning: <findings or none, or n/a>
  Release readiness: <findings or none, or n/a>
Confirmed vs assumed: <split>
Tests run or recommended: <list>
Verdict: keep | rewrite | revert
Reason: <short>
```

## Stop conditions

* Return `revert` if the diff exposes secrets, breaks sandbox confinement, enables wrong-answer cache reuse, or corrupts persistence.
* Return `rewrite` if behavior changed unintentionally or a high-risk path lost test coverage.
* Do not approve a high-risk diff without running its domain agents.
* Do not edit code from this skill. Review and verdict only.
