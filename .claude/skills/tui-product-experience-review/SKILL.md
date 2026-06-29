---
name: tui-product-experience-review
description: Review the Orchestrator CLI Textual TUI for the V2 product mental model. Enforces a sources, benchmarks, scorecards, routing, traces workflow, no fake metrics, clearly marked placeholders, an experimental agent-mode warning, keyboard-first UX, and subtle motion only where useful.
---

# tui-product-experience-review

## When to use

* Designing or reviewing the `design/tui-v2-workbench-experience` branch.
* Any change to `cli/tui/` that affects layout, workflow, or displayed data.
* When the TUI starts to show benchmark or scorecard surfaces.

## Goal

A TUI that reflects the real product workflow (sources, benchmarks, scorecards, routing, traces), shows only honest data, marks unbuilt areas as placeholders, and is fast and keyboard-first.

## Non-goals

* Not backend behavior (route, cache, providers live in core and services).
* Not motion-only review (use motion-interaction-reviewer for animation specifics).
* Not CLI command surface correctness (cli-interface-reviewer owns parity and exit codes).

## Inputs required

* `cli/tui/app.py`, `cli/tui/dispatcher.py`, `cli/tui/widgets.py`, `cli/tui/style.tcss`.
* `docs/product/PRODUCT_DIRECTION.md` and `docs/product/MVP_V2_SCOPE.md`.
* The "Product identity (V2)" section of `.claude/CLAUDE.md`.

## Review steps

1. Confirm the layout maps to the product mental model: sources, benchmarks, scorecards, routing, traces. The user should be able to see and move through that workflow.
2. Confirm every displayed metric is real and computed from actual data. No invented numbers, no sample dashboards passed off as live.
3. Confirm anything not yet implemented is clearly marked as a placeholder or "planned," not shown as working.
4. Confirm agent mode carries an experimental warning where it is reachable.
5. Confirm keyboard-first UX: discoverable bindings, history, escape, quit, no mouse requirement.
6. Confirm motion (if any) is subtle, purposeful, non-blocking, and does not slow the terminal.
7. Confirm CLI and TUI parity for shared workflows.

## Red flags

* Hardcoded or mocked metrics presented as live.
* A benchmark or scorecard panel that looks functional but is not wired.
* Agent mode reachable with no experimental warning.
* Mouse-only actions, or bindings that are not discoverable.
* Animation that blocks input or churns the terminal.

## Output format

```
Scope: <files>
Mental-model fit: sources/benchmarks/scorecards/routing/traces, present and navigable?
Data honesty: all metrics real? placeholders marked? <findings>
Agent-mode warning: present where reachable? yes/no
Keyboard-first UX: <findings>
Motion: subtle and non-blocking? <findings or n/a>
CLI/TUI parity: <findings>
Verdict: keep | fix | reject
Required reviewers: tui-product-designer, cli-interface-reviewer, motion-interaction-reviewer, qa-sdet-lead
```

## Stop conditions

* Reject any fake or mocked metric shown as live.
* Reject any unbuilt surface presented as working.
* Reject agent mode reachable without an experimental warning.
* Do not edit code from this skill.

## Example invocation

"Use tui-product-experience-review on the new scorecards panel layout."
