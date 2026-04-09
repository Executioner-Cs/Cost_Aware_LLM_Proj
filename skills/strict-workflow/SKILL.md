## Skill: Strict workflow (no shortcuts)

### When to use

Use this skill for any non-trivial change (feature slice, refactor, provider work, agent/tool work, cache changes, docs updates tied to behavior).

### Goal

Ensure every change is:
- implemented fully (no pseudocode for runtime)
- tested honestly (no weakened assertions)
- shipped via branch → commits → push → PR

### Absolute rules

- **Activate `.venv`** before any install/test.
- **No direct work on `main`** for feature slices.
- **No secrets** in git (never commit `.env`, API keys, tokens, real credentials).
- If an issue arises, **stop and plan** before changing code blindly.

### Procedure

1. **Prep**
   - `python -m venv .venv` (if missing)
   - PowerShell: `.\.venv\Scripts\Activate.ps1`
   - Install: `pip install -e ".[dev]"`

2. **Branch**
   - `git checkout -b feat/<topic>`

3. **Implement**
   - Keep changes minimal and coherent.
   - If something is intentionally unimplemented, fail explicitly (raise) and add tests that reflect that reality.

4. **Test (real)**
   - `.\.venv\Scripts\python.exe -m pytest -q`
   - If failures occur:
     - identify root cause
     - change code/tests to reflect true behavior
     - re-run until green

5. **Docs**
   - Update `README.md` for user-facing behavior/commands.
   - Update `CLAUDE.md` for architecture + invariants.

6. **Commit discipline**
   - Split commits by intent:
     - deps/spec
     - implementation + tests
     - docs

7. **Push + PR**
   - `git push -u origin HEAD`
   - PR must include:
     - summary of changes
     - how to run tests
     - proof tests passed

### Definition of done

- `git status` is clean
- tests are green under `.venv`
- docs reflect reality (no aspirational claims)

