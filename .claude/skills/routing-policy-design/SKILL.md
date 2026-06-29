---
name: routing-policy-design
description: Design and review routing hard filters, scoring, policy modes, fallback chains, and route explanations for Orchestrator CLI. Enforces cheapest-capable not cheapest-overall, a quality floor, privacy and capability hard filters, scorecard-fed scoring, and explained decisions.
---

# routing-policy-design

## When to use

* Designing or reviewing the `routing/policy-engine-v1` branch.
* Any change to how a model is selected, ranked, or filtered.
* Adding policy modes, fallback chains, or route explanations.

## Goal

A routing policy engine that applies hard filters, then scores survivors, produces a fallback chain, and explains why the chosen model won. Cheapest capable, never cheapest at the cost of capability or quality.

## Non-goals

* Not benchmark data production (use benchmark-scorecard-design); the policy consumes scorecards when present.
* Not the ModelSource abstraction (use model-source-design).
* Not a black-box ranking; explanations are part of the deliverable.

## Inputs required

* `core/model_selector.py` and `core/router.py` (current selection logic).
* The Scorecard and RoutingPolicy concepts in `docs/architecture/ORCHESTRATOR_V2_ARCHITECTURE.md`.
* The "Strategic direction" and "Non-negotiable product rules" sections of `.claude/CLAUDE.md`.

## Review steps

1. Confirm hard filters run first and remove models that cannot satisfy the request: context window, JSON support, tool support, privacy or local-only.
2. Confirm a quality floor exists so cost cannot select a model that fails the task.
3. Confirm scoring ranks survivors using scorecards (when present) plus cost, latency, and reliability, under the active policy mode.
4. Confirm the result is cheapest capable within constraints, not cheapest overall.
5. Confirm a fallback chain is produced for when the primary fails a filter or a call.
6. Confirm every decision carries a human-readable explanation of why the model won and what the fallbacks were.
7. Confirm behavior without scorecards is sensible (graceful degradation to cost-and-capability routing).

## Red flags

* Cost minimized before capability and quality are guaranteed.
* Hard constraints (context, JSON, tools, privacy) treated as soft preferences.
* No fallback chain, or a fallback that ignores the same hard filters.
* A decision with no explanation.
* Scorecards ignored when present, or required when absent (no graceful path).

## Output format

```
Scope: <files>
Filter-then-score order: confirmed? yes/no
Hard filters present: context | JSON | tools | privacy/local (list)
Quality floor: present? evidence
Scoring inputs: scorecards + cost + latency + reliability, present?
Cheapest-capable (not cheapest-overall): confirmed? yes/no
Fallback chain: present and filter-consistent? yes/no
Explanation: every decision explained? yes/no
Verdict: keep | fix | reject
Required reviewers: routing-policy-architect, business-logic-reviewer, provider-integration-reviewer, qa-sdet-lead
```

## Stop conditions

* Reject any policy that can select a model failing a hard constraint.
* Reject any routing decision that cannot be explained.
* Stop and flag if the change alters current routing behavior without tests pinning it.
* Do not edit code from this skill.

## Example invocation

"Use routing-policy-design to review the privacy-first policy mode design."
