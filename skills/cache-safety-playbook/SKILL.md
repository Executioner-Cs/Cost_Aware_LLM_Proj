## Skill: Cache safety playbook (semantic cache correctness)

### When to use

Use this skill when changing or relying on:
- `core/semantic_cache.py`
- cache thresholds in config
- any logic that may alter cache hit/miss behavior
- any prompt canonicalization intended to increase hit rates

### Goal

Maximize **safe cache hits** while minimizing “wrong-answer reuse”.

### Invariants (do not break)

- Cache hits must require:
  1. similarity ≥ threshold
  2. **exact** `task_type` match
  3. **exact** `quality` match
- Agent turns **must not** use semantic cache.

### Guardrails by task type

#### `json_extract`

- Prefer higher thresholds (e.g. `≥ 0.95`) because small prompt changes can change required fields.
- Validate cached output is parseable JSON and matches expected schema if known.

#### `reasoning`

- Slightly stricter than simple tasks is often safer.
- Beware of “related but different” tradeoffs; similarity can be high while intent differs.

#### `simple`

- Broadly safe for semantic caching.

### When to bypass cache (even if similar)

- Prompt contains explicit “must be up-to-date” or date-sensitive instructions.
- Prompt requests a **different set of fields** than the cached entry (structured tasks).
- Prompt references a different document/body (e.g. the user pasted new text).

### How to tune thresholds safely

1. Start with tests:
   - Add/adjust tests for hit/miss on carefully chosen prompt pairs.
2. Tune per task type first (not global).
3. Inspect trace similarity on real hits before lowering any threshold.
4. If you lower thresholds, add new tests for “nearby but wrong” prompts to prevent regressions.

