from __future__ import annotations

from types import SimpleNamespace

from utils import setup_ui


def test_supports_unicode_art_utf_encoding(monkeypatch):
    fake_console = SimpleNamespace(encoding="utf-8")
    monkeypatch.setattr(setup_ui, "console", fake_console)
    assert setup_ui._supports_unicode_art() is True


def test_supports_unicode_art_cp1252_false(monkeypatch):
    fake_console = SimpleNamespace(encoding="cp1252")
    monkeypatch.setattr(setup_ui, "console", fake_console)
    assert setup_ui._supports_unicode_art() is False


def _render(monkeypatch, fn, *args):
    import io
    from rich.console import Console

    buf = io.StringIO()
    monkeypatch.setattr(setup_ui, "console", Console(file=buf, width=200))
    fn(*args)
    return buf.getvalue().lower()


def test_init_banner_does_not_overclaim(monkeypatch):
    # Exact-cache default: init creates no vector store and downloads no model,
    # and there is no semantic cache. The setup copy must not claim otherwise.
    out = _render(monkeypatch, setup_ui.render_init_banner)
    for word in ("semantic", "vector", "embedding", "qdrant", "download"):
        assert word not in out, f"init banner still claims '{word}'"


def test_init_success_panel_does_not_claim_vector_store(monkeypatch, tmp_path):
    out = _render(monkeypatch, setup_ui.render_init_success_panel, tmp_path)
    assert "qdrant" not in out
    assert "vector" not in out

