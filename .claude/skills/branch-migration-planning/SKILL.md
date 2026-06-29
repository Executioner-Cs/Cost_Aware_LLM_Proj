---
name: branch-migration-planning
description: Plan a small, single-concern branch for the Orchestrator CLI V2 migration. Enforces one branch one concern, explicit out-of-scope, a definition of done, a rollback plan, and required tests, with no mega rewrites.
---

# branch-migration-planning

## When to use

* Before starting any branch in the accepted V2 roadmap.
* When a change feels like it spans more than one concern and needs splitting.
* When a plan risks becoming a mega rewrite.

## Goal

Produce a tight plan for one branch that does exactly one concern, with clear boundaries, a definition of done, a rollback path, and a test plan. See `docs/roadmap/BRANCH_ROADMAP.md`.

## Non-goals

* Not a design review of the feature itself (use system-design-review or the matching V2 architect).
* Not implementation. Planning only.
* Does not approve high-risk work; that still needs the review board and confirmation.

## Inputs required

* The branch name and the concern it owns.
* `docs/roadmap/BRANCH_ROADMAP.md` and the "Branch discipline" and "Current active branch guidance" sections of `.claude/CLAUDE.md`.
* The current `git status` and branch.

## Review steps

1. Name the single concern this branch owns. If there is more than one, split into multiple branches and stop.
2. List in-scope changes (files and behavior) and explicit out-of-scope items pulled from neighboring branches.
3. State the behavior to preserve and what is allowed to change.
4. Define the definition of done in observable terms.
5. Define the test plan (specific pytest files where possible; note gaps and manual checks).
6. Define the rollback plan: how to revert cleanly and what to watch after.
7. Map the required reviewers from the V2 routing matrix.

## Red flags

* A branch that touches security, packaging, routing, source abstraction, evals, and TUI at once.
* No explicit out-of-scope list.
* A definition of done that is not observable or testable.
* Schema or dependency changes hidden inside an unrelated branch.
* "While I am here" changes outside the concern.

## Output format

```
Branch: <name>
Single concern: <one sentence>
In scope: <files and behavior>
Out of scope (belongs to other branches): <list>
Behavior to preserve: <list>
Definition of done: <observable criteria>
Tests/checks: <pytest files and manual checks; gaps noted>
Rollback plan: <steps>
Required reviewers: <agent list>
Confirmation required: yes | no
```

## Stop conditions

* Stop and split if the branch owns more than one concern.
* Stop if the plan changes behavior with no test or characterization check.
* Stop for confirmation before any high-risk branch (security, schema, routing, dependencies).
* Do not edit code from this skill.

## Example invocation

"Use branch-migration-planning to scope architecture/model-source-abstraction before I start."
