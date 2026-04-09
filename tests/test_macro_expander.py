from __future__ import annotations

import pytest

from agent.macro_expander import expand_macros, parse_goal_macros


def test_parse_goal_macros_no_block_returns_original():
    parsed, stripped = parse_goal_macros("Implement X")
    assert parsed is None
    assert stripped == "Implement X"


def test_parse_goal_macros_parses_flags_and_strips_goal():
    parsed, stripped = parse_goal_macros("{BRPR,VENV,NOFAKE}  Implement X  ")
    assert parsed is not None
    assert stripped == "Implement X"
    assert "BRPR" in parsed.flags
    assert "VENV" in parsed.flags
    assert "NOFAKE" in parsed.flags


def test_parse_goal_macros_parses_sizes():
    parsed, stripped = parse_goal_macros("{CX:2048,TOOLSUM:1K} Do thing")
    assert parsed is not None
    assert stripped == "Do thing"
    assert parsed.cx_chars == 2048
    assert parsed.toolsum_chars == 1024


def test_parse_goal_macros_rejects_invalid_size():
    with pytest.raises(ValueError):
        parse_goal_macros("{CX:two} X")


def test_expand_macros_empty_is_blank():
    parsed, _ = parse_goal_macros("{} X")
    assert parsed is not None
    assert expand_macros(parsed) == ""


def test_expand_macros_includes_flag_text():
    parsed, _ = parse_goal_macros("{BRPR,DOCSYNC} X")
    text = expand_macros(parsed)  # type: ignore[arg-type]
    assert "Macro constraints" in text
    assert "BRPR" in text
    assert "DOCSYNC" in text

