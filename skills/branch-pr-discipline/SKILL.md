## Skill: Branch → Commit → PR discipline

### When to use

Use this skill whenever you are about to implement a **feature slice** (anything more than a trivial edit), especially if it changes behavior, adds dependencies, or touches multiple files.

### Goal

Ship changes in a way that is:
- **reproducible** (tests are real and run in the project venv)
- **reviewable** (small commits with clear intent)
- **safe** (no secrets committed; no “fake green”)

### Non-goals

- Skipping tests “because it should work”
- Using placeholders, pseudocode, or TODOs for core behavior
- Hiding failures by weakening tests

### Procedure

1. **Create and activate venv**
   - Create `.venv` if missing: `python -m venv .venv`
   - Activate it (PowerShell): `.\.venv\Scripts\Activate.ps1`

2. **Create a feature branch**
   - `git checkout -b feat/<short-topic>`

3. **Implement the feature fully**
   - No pseudocode for runtime paths
   - If a provider/tool is not implemented, it must fail **explicitly and loudly** (e.g., raise `NotImplementedError`) and tests must reflect reality.

4. **Run tests using venv Python**
   - `.\.venv\Scripts\python.exe -m pytest -q`
   - If anything fails, fix it (do not “paper over”).

5. **Commit in logical chunks**
   - Prefer separate commits for:
     - dependency spec changes
     - implementation + tests
     - documentation

6. **Push branch and open PR**
   - `git push -u origin HEAD`
   - Create PR with summary + test evidence.

7. **Only after merge**
   - `git checkout main`
   - `git pull`

### Acceptance checks

- `git status` is clean
- tests are green (and were run under `.venv`)
- README / `CLAUDE.md` reflect new features and current constraints

