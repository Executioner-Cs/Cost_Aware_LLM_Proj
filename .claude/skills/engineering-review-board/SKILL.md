---
name: engineering-review-board
description: Coordinate senior reviewer agents for medium and high-risk Orchestrator CLI changes, gate on confirmation before high-risk edits, and deliver a keep/rewrite/revert verdict after.
---

# engineering-review-board

## Purpose

Coordinate senior reviewers for medium and high-risk tasks. Run the right agents before coding, gate on user confirmation for high-risk work, then run a post-change gate and issue a final verdict.

## When to use

* Medium-risk and high-risk changes as classified by `agent-routing`.
* Changes spanning more than one domain (for example a provider change that also touches schemas and the router).
* Any change to agent execution, sandbox, secrets, cache correctness, provider routing, or DB persistence.

## Required pre-read

* `.claude/CLAUDE.md` (routing matrix, high-risk areas, review board policy).
* The output of `agent-routing` for this task.
* The target files and their current `git diff` if work has started.

## Required agents

Selected per domain from the routing matrix in `.claude/CLAUDE.md`. Common sets:

* agent runtime: agent-runtime-architect, security-architect, behavior-preservation-checker, qa-sdet-lead
* sandbox/file access: security-architect, agent-runtime-architect, qa-sdet-lead
* provider integration: provider-integration-reviewer, api-contract-architect, qa-sdet-lead
* cache/embeddings: embeddings-retrieval-reviewer, behavior-preservation-checker, qa-sdet-lead
* database: database-persistence-reviewer, security-architect, behavior-preservation-checker, qa-sdet-lead
* schema/contract: api-contract-architect, behavior-preservation-checker, qa-sdet-lead

V2 domain sets (agents marked pending may not exist yet; use the closest existing reviewer and note the gap):

* docs/product positioning: product-strategy-reviewer, docs-product-positioning-reviewer, slop-hunter
* dependency slimming and cache tiers: python-packaging-reviewer, cache-architecture-reviewer, embeddings-retrieval-reviewer, database-persistence-reviewer, qa-sdet-lead
* ModelSource: model-source-architect, provider-integration-reviewer, api-contract-architect, database-persistence-reviewer
* routing policy and scoring: routing-policy-architect, business-logic-reviewer, provider-integration-reviewer, qa-sdet-lead
* benchmarks and scorecards: benchmark-evals-architect, database-persistence-reviewer, qa-sdet-lead
* TUI product experience: tui-product-designer, cli-interface-reviewer, motion-interaction-reviewer, qa-sdet-lead
* release readiness: release-readiness-manager, behavior-preservation-checker

Architecture-level changes also pull in principal-system-architect.

## Process

1. Before coding (review phase):
   * Confirm risk and affected domains from `agent-routing`.
   * Run the required agents as read-only reviewers on the current code and the proposed plan.
   * Collect findings, separating confirmed issues from assumptions.
2. Confirmation gate:
   * For high-risk tasks, present the plan, risks, and reviewer findings to the user and stop for explicit approval.
   * For medium-risk tasks that change visible behavior, request approval; otherwise note the decision and proceed.
3. Implementation (only after approval): main Claude implements. Agents do not edit code.
4. Post-change gate:
   * Run behavior-preservation-checker on the diff.
   * Run qa-sdet-lead for regression and test gaps.
   * Run readability or slop review.
   * Run the domain agents again on the diff.
5. Final verdict.

## Output format

```
Phase: before-coding | post-change
Risk: Medium | High
Agents run: <list>
Confirmed findings: <list with file:symbol>
Assumptions: <list>
Confirmation gate: pending | approved | not required
Verdict: keep | rewrite | revert
Reason: <short>
```

## Stop conditions

* Stop at the confirmation gate for all high-risk tasks; do not implement without explicit user approval.
* Stop and recommend revert if the post-change gate finds an unmitigated high-risk regression (broken sandbox confinement, secret exposure, wrong-answer cache reuse, lost DB integrity).
* Do not let the board edit code. Implementation belongs to main Claude after approval.
