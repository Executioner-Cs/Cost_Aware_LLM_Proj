# v0.2 Local Run Verification

A from-clean local verification that Orchestrator CLI installs, runs, and tests pass, using an isolated environment and no real provider keys or network calls.

## 1. Environment

* OS: Windows 11 Pro (10.0.26200).
* Python: 3.13.4 (project requires 3.11+).
* venv path: `.venv-v02-smoke` (a clean virtual environment created for this audit, separate from any existing `.venv`).
* Install commands:
  * `python -m venv .venv-v02-smoke`
  * `.venv-v02-smoke/Scripts/python.exe -m pip install --upgrade pip`
  * Base + dev: `.venv-v02-smoke/Scripts/python.exe -m pip install -e ".[dev]"`
  * Full suite: `.venv-v02-smoke/Scripts/python.exe -m pip install -e ".[all,dev]"`
* Isolated app home: `ORCHESTRATOR_HOME` was set to a temporary directory for every CLI command. The real user home (`~/.orchestrator`) was never touched.

## 2. Test results

* Slim `[dev]` install: full `pytest` cannot collect 4 files that import optional extras (`test_openai_adapter_tools.py`, `test_gemini_adapter_tools.py`, `test_tui_app.py`, `test_output_styles_and_ci_modes.py`). Expected: the README documents that the full suite needs `[all,dev]`. The slim install is for running the product, not the whole suite.
* `[all,dev]` install (clean): 1 collection error remains, `test_output_styles_and_ci_modes.py`, because it does `import click` and `click` is not a declared dependency (see Section 6).
* `[all,dev]` + `click` present: **300 passed**.
* Import-purity probe: PASS. With `torch`, `sentence-transformers`, `qdrant-client`, and `transformers` forced unavailable, `core.cache`, `core.router`, and `cli.main` import cleanly and none of the heavy modules load. The default route path is slim.

## 3. CLI smoke tests (isolated ORCHESTRATOR_HOME)

| Command | Result | Notes |
|---|---|---|
| `orchestrator --help` | exit 0 | Top-level help renders. |
| `orchestrator init` | exit 0 | Creates only `config.toml` + `orchestrator.db`. No Qdrant dir, no model download (exact-cache default). |
| `orchestrator model --help` | exit 0 | |
| `orchestrator model list` | exit 0 | Empty registry (no accounts connected). |
| `orchestrator cache --help` | exit 0 | |
| `orchestrator cache stats` | exit 0 | Shows Mode: exact, Total entries: 0. |
| `orchestrator trace --help` | exit 0 | |
| `orchestrator trace list` | exit 0 | Empty trace list. |
| `orchestrator route --help` | exit 0 | Flags: `--task`, `--quality`, `--dry-run`. |
| `orchestrator accounts --help` | exit 0 | |
| `orchestrator connect --help` | exit 0 | Supports cloud providers and `--base-url` local/OpenAI-compatible sources. |
| `orchestrator benchmark --help` | exit 0 | `create`, `add-task`, `run`, `scorecards`. |
| `orchestrator agent --help` | exit 0 | Experimental agent commands. |

All smoke commands ran on the slim `[dev]` install (no provider SDKs, no TUI, no ML), confirming the base product runs without optional extras.

## 4. What works locally (verified)

* A clean `pip install -e ".[dev]"` produces a working `orchestrator` CLI with no heavy ML, vector, provider-SDK, or TUI packages installed.
* `orchestrator init` provisions a local SQLite database and config under an isolated home, using the exact-match cache (no embedding model download, no vector store).
* `model list`, `cache stats`, `trace list` run against the local database with no accounts connected.
* Every command group exposes working `--help`.
* The default route path imports no heavy dependencies (import-purity probe).
* The full test suite passes (300) when `click` is available.

## 5. What feels good

* The slim install is genuinely slim and fast: base + dev pulls no torch/Qdrant/provider SDKs.
* `init` is honest and lightweight in exact mode: it does not silently download a model or spin up a vector store.
* Command help is clear and the command surface (route, model, cache, trace, accounts, connect, benchmark, agent) reads as a coherent workbench.
* Cache status is transparent (`Mode: exact`).

## 6. What feels rough

* Undeclared `click` dependency in the test suite. `tests/tests_e2e_cli_simulation/test_output_styles_and_ci_modes.py` does `import click`, but `click` is not a project or dev dependency. Modern `typer` (0.26.x here) no longer depends on `click`, so a clean `pip install -e ".[all,dev]"; pytest` fails to collect that one file. The product does not need `click` (the CLI ran fine without it); only that test does. Suggested fix (small, outside this audit's docs-only scope): add `click` to the `dev` extra, or remove the direct `import click` from the test. This is the only thing standing between a clean environment and a green full suite.
* `[dev]` alone cannot run the full test suite. Running `pytest` after `pip install -e ".[dev]"` produces 4 collection errors for the provider-adapter and TUI tests. The README does document `pip install -e ".[all,dev]"` for the full suite, but the `[dev]`-then-`pytest` path is an easy trap.
* TUI not exercised here. The TUI requires the `[tui]` extra and is interactive; only `--help`-level and non-TUI commands were smoke-tested.

## 7. What was not tested

* Real cloud providers (Anthropic, OpenAI, Groq, Gemini): no real API keys, no live calls.
* Real Ollama: not detected or invoked; not relied on for any PASS.
* Real OpenAI-compatible endpoint: command help and config flow only; no live endpoint.
* Interactive TUI behavior: not driven interactively.
* Benchmarks against real models: only deterministic local tests in the suite cover scoring.

## 8. New developer quickstart

```bash
# 1. Clone
git clone https://github.com/Executioner-Cs/Cost_Aware_LLM_Proj.git
cd Cost_Aware_LLM_Proj

# 2. Clean virtual environment (.venv is git-ignored)
python -m venv .venv
# Windows PowerShell:  .\.venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate

# 3. Install. Base + dev runs the CLI; add [all] to run the whole test suite.
pip install -e ".[all,dev]"

# 4. Run the tests
pytest

# 5. Initialize against an isolated home (does not touch ~/.orchestrator)
#    Windows PowerShell:  $env:ORCHESTRATOR_HOME = "$env:TEMP\orch_demo"
#    macOS / Linux:       export ORCHESTRATOR_HOME="$(mktemp -d)"
orchestrator init

# 6. Smoke the CLI (no provider keys needed)
orchestrator --help
orchestrator model list
orchestrator cache stats
orchestrator trace list
orchestrator route --help
```

## 9. Release recommendation

**WARN** for tagging v0.2.0.

* Product runtime: PASS. The CLI installs slim, runs end to end against an isolated home, keeps the default path free of heavy dependencies, and the full test suite passes (300) when `click` is present.
* The single blocker to a clean contributor experience is the undeclared `click` test dependency (Section 6): a from-scratch `pip install -e ".[all,dev]"; pytest` fails one collection. This is a one-line packaging fix (add `click` to the `dev` extra or drop the test's direct import), not a product defect.
* Recommendation: make that small dependency fix before or together with the tag so the documented test flow works in a clean environment, then tag. No runtime code change is required.
