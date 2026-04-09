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

