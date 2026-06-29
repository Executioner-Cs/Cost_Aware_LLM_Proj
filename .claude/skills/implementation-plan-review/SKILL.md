---
name: implementation-plan-review
description: Review a proposed implementation plan for an Orchestrator CLI change before any edit. Covers affected files, behavior to preserve, risk, required reviewers, tests, rollback, and a confirmation gate.
---

# implementation-plan-review

## Purpose

Review a proposed implementation plan before edits are made. Catch scope, risk, and behavior-preservation problems on paper, where they are cheap to fix.

## When to use

* Before implementing any medium or high-risk change.
* CLI destructive behavior changes and packaging/build changes (per the routing matrix).
* When a change touches more than one file or more than one domain.

## Required pre-read

* `.claude/CLAUDE.md` (architecture expectations, invariants, routing matrix).
* The files the plan intends to change.
* Existing tests covering those files (`tests/`, including `tests/tests_e2e_cli_simulation/`).

## Required agents

* behavior-preservation-checker (always).
* Domain agents for the affected area (from the routing matrix).
* refactor-test-strategist when the plan claims tests will cover the change.

## Process

1. List the affected files and the symbols that will change.
2. State the behavior that must be preserved (routing decisions, cache hit/miss, provider contracts, CLI output and exit codes, DB writes, sandbox limits).
2a. Branch-scope check: confirm the plan stays within the current branch's single concern per the "Current active branch guidance" in `.claude/CLAUDE.md`. Flag any work that belongs to a different branch (for example schema or provider changes on a docs branch, or routing changes on a cache branch) and move it out of scope.
3. Assign a risk level using the `agent-routing` scale, and select reviewers from both the original routing matrix and the "Branch-to-agent routing (V2)" section in `.claude/CLAUDE.md`.
4. List the agents that must review and what each will check.
5. List the tests and checks to run (specific pytest files where possible; note when none exist).
6. Define a rollback plan (how to revert cleanly, what to watch after).
7. Apply the confirmation gate.

## Output format

```
Plan summary: <short>
Affected files: <path list with symbols>
Behavior to preserve: <list>
Risk: Low | Medium | High
Required reviewers: <agent list with focus>
Tests/checks: <specific commands and pytest files; note gaps>
Rollback plan: <steps>
Confirmation required: yes | no
```

## Stop conditions

* Stop for user confirmation before implementing any high-risk plan.
* Stop if the plan changes behavior that has no test coverage and the plan does not add a characterization test or a manual check.
* Stop if the plan would deepen `core -> services` coupling, weaken sandbox confinement, or alter cache hit criteria without explicit justification.
* Do not edit code from this skill. Plan review only.
