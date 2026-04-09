"""Smoke tests for the OrchestratorApp TUI."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from textual.widgets import Input

from cli.tui.app import SessionState, bootstrap_state


@pytest.fixture
def app():
    from cli.tui.app import OrchestratorApp

    return OrchestratorApp()


# ── Startup / welcome ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_app_starts_and_shows_welcome(app):
    """App mounts and displays the welcome banner."""
    async with app.run_test(size=(120, 40)) as pilot:
        log = app.query_one("#output")
        assert log is not None
        inp = app.query_one("#cmd-input")
        assert inp is not None


@pytest.mark.asyncio
async def test_prompt_placeholder_shows_orchestrator(app):
    """The input placeholder contains 'orchestrator >'."""
    async with app.run_test(size=(120, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        assert "orchestrator" in inp.placeholder.lower()


# ── Command execution ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_help_command(app):
    """Typing 'help' + Enter writes help text into the output log."""
    async with app.run_test(size=(120, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        inp.value = "help"
        await pilot.press("enter")
        await pilot.pause()


@pytest.mark.asyncio
async def test_unknown_command(app):
    """Unknown commands produce an error message, not a crash."""
    async with app.run_test(size=(120, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        inp.value = "xyzzy"
        await pilot.press("enter")
        await pilot.pause()


@pytest.mark.asyncio
async def test_exit_command(app):
    """Typing 'exit' triggers app exit."""
    async with app.run_test(size=(120, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        inp.value = "exit"
        await pilot.press("enter")
        await pilot.pause()


@pytest.mark.asyncio
async def test_empty_input_ignored(app):
    """Pressing Enter on empty input does nothing."""
    async with app.run_test(size=(120, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        inp.value = ""
        await pilot.press("enter")
        await pilot.pause()


# ── Key bindings ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_escape_clears_input(app):
    """Pressing Escape clears the input field."""
    async with app.run_test(size=(120, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        inp.value = "some text"
        assert inp.value == "some text"
        await pilot.press("escape")
        assert inp.value == ""


@pytest.mark.asyncio
async def test_ctrl_c_clears_input_instead_of_exit(app):
    """Ctrl+C clears input; app stays alive."""
    async with app.run_test(size=(120, 40)) as pilot:
        inp = app.query_one("#cmd-input", Input)
        inp.value = "some text"
        await pilot.press("ctrl+c")
        assert inp.value == ""


# ── Bootstrap state ──────────────────────────────────────────────────

class TestSessionState:
    def test_default_values(self):
        s = SessionState()
        assert s.initialised is False
        assert s.provider_count == 0
        assert s.cache_enabled is True
        assert s.default_quality == "balanced"

    def test_bootstrap_no_home_returns_uninitialised(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCHESTRATOR_HOME", str(tmp_path / "missing"))
        state = bootstrap_state()
        assert state.initialised is False

    def test_bootstrap_with_config_returns_initialised(self, tmp_path, monkeypatch):
        home = tmp_path / ".orchestrator"
        home.mkdir()
        (home / "config.toml").write_text(
            '[cache]\nenabled = true\n[routing]\ndefault_quality = "cheap"\n[cost]\n'
        )
        monkeypatch.setenv("ORCHESTRATOR_HOME", str(home))
        with patch("db.session.get_session", side_effect=Exception("no db")):
            state = bootstrap_state()
        assert state.initialised is True
        assert state.default_quality == "cheap"
        assert state.cache_enabled is True


# ── Subtitle refresh ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subtitle_updates_after_bootstrap(app):
    """After mount the subtitle should contain status keywords."""
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        subtitle = app.sub_title
        assert "models" in subtitle or "provider" in subtitle
