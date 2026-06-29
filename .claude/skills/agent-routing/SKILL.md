---
name: agent-routing
description: Classify a task for Orchestrator CLI by risk and affected domains, then route it to the right Claude Code skill and reviewer agents before any edit. Use first on every non-trivial change.
---

# agent-routing

## Purpose

Classify tasks and route them to the right skills and agents. This is the entry point for the senior engineering review board. Run it before touching code so risk and reviewers are decided up front, not after.

## When to use

* At the start of any non-trivial change in this repo.
* Whenever the user asks for a feature, fix, refactor, or review and the affected domain is not yet obvious.
* Before selecting any other skill.
* Skip only for trivial docs or comment-only edits (state that you are skipping and why).

## Required pre-read

* `.claude/CLAUDE.md` (routing matrix, high-risk areas, required workflow).
* The specific files named in the user request.
* `git status` and `git diff` if a change is already in progress.

## Required agents

This skill selects agents; it does not run them. After classification, hand off to `engineering-review-board`, `system-design-review`, `implementation-plan-review`, or `post-change-review` as appropriate, which invoke the domain agents.

## Process

1. Restate the task in one or two sentences.
2. Classify risk:
   * Low: docs, comments, isolated test additions, output string tweaks with no behavior change.
   * Medium: localized logic changes in one domain that do not touch secrets, sandbox, routing correctness, cache hit/miss, or persistence schema.
   * High: anything touching agent execution, sandbox confinement, secrets/keys, prompt/tool injection surfaces, semantic cache correctness, provider routing/pricing, DB schema or dual-store writes, cross-provider tool mapping, destructive CLI commands, or packaging/release behavior.
3. Detect affected domains by mapping changed or target files to the routing matrix in `.claude/CLAUDE.md`. Domains include the original set (agent runtime, sandbox/file access, provider integration, cache/embeddings, database, CLI, schema/contract, refactor, packaging) and the V2 set (docs/product positioning, dependency slimming and cache tiers, ModelSource, routing policy and scoring, benchmarks and scorecards, TUI product experience, release readiness).
4. Select the skill and the required agents from the routing matrix for each affected domain, using both the original "Routing matrix" and the "Branch-to-agent routing (V2)" section in `.claude/CLAUDE.md`. Union the agent sets if multiple domains apply. On any docs or product-facing change, also apply `product-direction-guard` so the change does not drift back into generic router, gateway, or coding-agent framing.
5. Decide confirmation: required for all High-risk work, and for Medium work that changes externally visible behavior.
6. State the behavior that must be preserved and the tests/checks to run.

## Output format

```
Task: <one or two sentences>
Risk: Low | Medium | High
Affected domains: <list>
Skill: <skill name>
Agents: <list of agent names>
Behavior to preserve: <list>
Tests/checks: <list>
Confirmation required: yes | no
```

## Stop conditions

* Stop and request user confirmation before proceeding on any High-risk task.
* Stop if the task touches secrets, keys, or sandbox confinement and the user has not explicitly approved the change.
* Stop if you cannot map the task to a domain with confidence; ask the user to clarify scope rather than guess.
* Do not edit code from this skill. Routing only.
