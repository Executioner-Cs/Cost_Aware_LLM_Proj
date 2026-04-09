## Skill: Macro hand-sign DSL (token-saving goal prefix)

### When to use

Use this skill when running `orchestrator agent ...` and you want to avoid spending tokens re-stating the same constraints (workflow discipline, venv rules, doc updates, context compaction).

### Goal

Express common constraints in a **compact prefix** that expands locally (no model tokens) into system-prompt instructions.

### Non-goals

- Encoding domain requirements that should live in code/tests
- Using macros to bypass safety (shell restrictions, sandbox, secret handling)

### Syntax (inline DSL)

Prefix the goal with a leading `{...}` block:

```
{BRPR,VENV,NOFAKE,DOCSYNC,CX:2048,TOOLSUM:1K} Implement feature X
```

Rules:
- The macro block is only parsed if it appears **at the very start** of the goal.
- Tokens are comma-separated.
- Flags are case-insensitive.
- Key/value tokens use `KEY:VALUE`.

### Supported macros (current)

#### Flags

- `BRPR`
  - Enforces branch→commit→push→PR discipline.
- `VENV`
  - Enforces activating `.venv` before installs/tests.
- `NOFAKE`
  - Disallows pseudocode, TODO placeholders for runtime paths, or weakening tests to “go green”.
- `DOCSYNC`
  - Requires updating `README.md` (user-facing) and `CLAUDE.md` (canonical) when behavior/architecture changes.

#### Parameters

- `CX:<n>`
  - Context compaction target for the running state summary.
  - Values: `2048`, `2K`, `1M` (characters).
- `TOOLSUM:<n>`
  - Target size for tool-output summaries pasted back into the conversation.
  - Values: `1K`, `4K`, etc (characters).

### Examples

Minimal, high-signal goal:

```
{BRPR,VENV,NOFAKE,DOCSYNC} Add provider X tool calling and tests
```

With compaction guidance:

```
{CX:2K,TOOLSUM:1K,NOFAKE} Fix failing tests without bloating context
```

### Troubleshooting

- If the agent appears to “ignore” macros, verify the block is at the **very start** of the goal and closed with `}`.

