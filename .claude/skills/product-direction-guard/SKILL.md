---
name: product-direction-guard
description: Guard Orchestrator CLI against scope drift back into generic router, gateway, cost-tracker, or coding-agent territory. Apply on any product, docs, feature, or positioning change to keep the local-first benchmark-driven workbench identity intact.
---

# product-direction-guard

## When to use

* Any change to README, docs, TUI copy, help text, or feature framing.
* Any new feature proposal, to check it advances the actual product.
* Whenever a change starts to sound like "add more providers" or "build a gateway" or "make it a coding agent."
* Before approving positioning or marketing language.

## Goal

Keep Orchestrator CLI on its defensible niche: a local-first AI routing and benchmarking workbench whose differentiator is benchmark-driven routing using the developer's own task sets and local scorecards. See `docs/product/PRODUCT_DIRECTION.md`.

## Non-goals

* Not a style or readability review (use refactor-readability or slop-hunter).
* Not a correctness review (use post-change-review).
* Does not block legitimate work on existing provider routing; it blocks drift in framing and scope.

## Inputs required

* The change or proposal under review (diff, doc, or description).
* `docs/product/PRODUCT_DIRECTION.md` and the "Product identity (V2)" and "Non-negotiable product rules" sections of `.claude/CLAUDE.md`.

## Review steps

1. Restate what the change claims the product is or does.
2. Check it against the identity: local-first, benchmark-driven routing, scorecards as the differentiator.
3. Check it against the non-negotiable rules: do not chase provider count, do not make API keys the identity, do not promote semantic cache as headline, do not promote agent mode before P0, do not invent implemented features, do not make heavy deps required for base routing, keep local-first.
4. Check the "what this is not" list: gateway, LiteLLM/OpenRouter clone, hosted dashboard, provider-count race, coding agent, plain cheapest-model router.
5. Confirm any planned feature is labeled planned and any implemented feature is documented accurately.

## Red flags

* Language that sells provider breadth as the value.
* The semantic cache or agent mode presented as the headline.
* Claims of network isolation or safe sandboxing that source does not enforce.
* A feature that only makes sense for a hosted or multi-user product.
* Planned features written as if they exist.
* "Just route to the cheapest model" framing with no quality, capability, or scorecard basis.

## Output format

```
Change under review: <short>
Identity fit: aligned | drifting | off-product
Rule checks:
  - <rule>: pass | fail, with evidence
What-this-is-not violations: <list or none>
Current vs planned accuracy: <ok or issues>
Verdict: keep | reframe | reject
Reason: <short>
```

## Stop conditions

* Reject and explain if the change repositions the product as a gateway, router-only, cost tracker, or coding agent.
* Reject any claim that a planned feature is implemented, or that an unenforced safety property is enforced.
* Do not edit code or docs from this skill; it is a guard, not an implementer.

## Example invocation

"Apply product-direction-guard to the new README features section before we commit it."
