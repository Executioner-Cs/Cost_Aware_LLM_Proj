"""
Packaging contract tests for the optional-dependency extras (Patch 2).

These assert the *packaging* promises that Patch 1's lazy-import code relies on:
base install stays light, the documented extras exist, a fresh interpreter
imports the CLI without any optional library, and a missing extra surfaces a
clean, actionable error rather than a raw ImportError.

Cache hit/miss behavior and the exact-default route path are covered by
test_exact_cache.py and are not repeated here.
"""
from __future__ import annotations

import builtins
import importlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Packages that must never be pulled in by a base install.
OPTIONAL_PACKAGES = {
    "sentence-transformers",
    "qdrant-client",
    "openai",
    "anthropic",
    "google-genai",
    "textual",
    "questionary",
}
# Their import-time module names, for the fresh-interpreter purity probe.
OPTIONAL_MODULES = [
    "torch",
    "sentence_transformers",
    "qdrant_client",
    "transformers",
    "openai",
    "anthropic",
    "google",
    "textual",
    "questionary",
]


def _req_name(requirement: str) -> str:
    """'sentence-transformers>=2.7' -> 'sentence-transformers'."""
    return re.split(r"[<>=!~;\[\s]", requirement, maxsplit=1)[0].strip().lower()


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# pyproject shape: light base, documented extras
# --------------------------------------------------------------------------- #

def test_base_dependencies_are_light(pyproject):
    base = {_req_name(r) for r in pyproject["project"]["dependencies"]}
    assert base == {
        "typer", "pydantic", "sqlalchemy", "httpx", "rich", "cryptography", "python-dotenv",
    }
    # No heavy/provider/TUI package leaked into the base.
    assert base.isdisjoint(OPTIONAL_PACKAGES)


def test_no_tomllib_marker_in_base(pyproject):
    # tomllib is stdlib from 3.11 and not a PyPI package; the floor is >=3.11.
    assert all(_req_name(r) != "tomllib" for r in pyproject["project"]["dependencies"])


def test_optional_extras_exist(pyproject):
    extras = pyproject["project"]["optional-dependencies"]
    assert set(extras) == {
        "tui", "openai", "anthropic", "gemini", "providers", "dev", "all",
    }
    # Legacy heavy semantic cache removed: no heavy-cache extra. No FastEmbed
    # light-cache alias, no groq extra.
    assert "heavy-cache" not in extras
    assert "cache" not in extras
    assert "groq" not in extras


def test_extra_membership(pyproject):
    extras = {k: {_req_name(r) for r in v} for k, v in pyproject["project"]["optional-dependencies"].items()}
    assert extras["tui"] == {"textual", "questionary"}
    assert extras["openai"] == {"openai"}
    assert extras["anthropic"] == {"anthropic"}
    assert extras["gemini"] == {"google-genai"}
    assert extras["providers"] == {"openai", "anthropic", "google-genai"}
    assert "heavy-cache" not in extras
    assert extras["all"] == {
        "textual", "questionary", "openai", "anthropic", "google-genai",
    }


def test_no_unplanned_packages_anywhere(pyproject):
    # Not added yet: sqlite-vec or FastEmbed (semantic-cache-v2 work).
    all_reqs = list(pyproject["project"]["dependencies"])
    for reqs in pyproject["project"]["optional-dependencies"].values():
        all_reqs.extend(reqs)
    names = {_req_name(r) for r in all_reqs}
    assert "sqlite-vec" not in names
    assert "fastembed" not in names


def test_no_vector_or_ml_stack_anywhere(pyproject):
    # Legacy heavy semantic cache removed: its vector/ML stack must not be a
    # declared dependency in any group (base or extras).
    all_reqs = list(pyproject["project"]["dependencies"])
    for reqs in pyproject["project"]["optional-dependencies"].values():
        all_reqs.extend(reqs)
    names = {_req_name(r) for r in all_reqs}
    for pkg in ("sentence-transformers", "qdrant-client", "torch", "transformers", "grpcio"):
        assert pkg not in names, f"{pkg} must not be declared after semantic v1 removal"


# --------------------------------------------------------------------------- #
# A fresh interpreter imports the CLI without any optional library
# --------------------------------------------------------------------------- #

def test_fresh_import_pulls_no_optional_libs():
    probe = (
        "import sys; import cli.main, core.router, core.cache, services.init_service; "
        f"bad=[m for m in {OPTIONAL_MODULES!r} if m in sys.modules]; "
        "sys.exit('LOADED:'+','.join(bad) if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).strip()


# --------------------------------------------------------------------------- #
# Missing provider SDK -> clean install hint (route path)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "provider,missing_module,extra",
    [
        ("openai", "openai", "openai"),
        ("anthropic", "anthropic", "anthropic"),
        ("gemini", "google", "gemini"),
        ("groq", "openai", "openai"),  # groq routes through the openai SDK
    ],
)
def test_missing_provider_sdk_maps_to_extra(monkeypatch, provider, missing_module, extra):
    from core import router
    from core.cache import MissingFeatureError

    def boom(path):
        raise ModuleNotFoundError(f"No module named '{missing_module}'", name=missing_module)

    monkeypatch.setattr(importlib, "import_module", boom)
    with pytest.raises(MissingFeatureError) as excinfo:
        router._get_adapter(provider)
    assert f'orchestrator-cli[{extra}]' in str(excinfo.value)


def test_unrelated_import_error_is_not_masked(monkeypatch):
    """A failure that is not a known provider SDK must propagate unchanged."""
    from core import router

    def boom(path):
        raise ModuleNotFoundError("No module named 'somethingelse'", name="somethingelse")

    monkeypatch.setattr(importlib, "import_module", boom)
    with pytest.raises(ModuleNotFoundError):
        router._get_adapter("openai")


# --------------------------------------------------------------------------- #
# Semantic mode was removed -> clear error pointing back to exact
# --------------------------------------------------------------------------- #

def test_semantic_mode_removed_gives_clean_error(tmp_path):
    from core.cache import get_cache, MissingFeatureError

    with pytest.raises(MissingFeatureError) as excinfo:
        get_cache({"cache": {"enabled": True, "mode": "semantic"}}, object(), tmp_path)
    message = str(excinfo.value)
    assert "Semantic cache v1 has been removed" in message
    assert 'cache.mode = "exact"' in message
    assert "semantic-cache-v2" in message


# --------------------------------------------------------------------------- #
# TUI launch without the tui extra -> clean message, non-zero exit
# --------------------------------------------------------------------------- #

def test_tui_missing_dependency_gives_clean_error(monkeypatch, capsys):
    import typer
    from cli import main as cli_main

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cli.tui.app" or name.split(".")[0] == "textual":
            raise ModuleNotFoundError("No module named 'textual'", name="textual")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(typer.Exit):
        cli_main._launch_tui()
    err = capsys.readouterr().err
    assert "tui extra" in err
    assert 'orchestrator-cli[tui]' in err
