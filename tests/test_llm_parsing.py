from __future__ import annotations

import pytest

from rosetta.llm import _strip_reasoning, extract_code, parse_json_loose


def test_strip_reasoning_block():
    assert _strip_reasoning("<think>musing</think>answer") == "answer"


def test_strip_unterminated_reasoning_block_keeps_tail():
    # A truncated response must not silently pass reasoning off as an answer.
    out = _strip_reasoning("<think>cut off mid thought")
    assert "cut off" in out


def test_extract_code_picks_largest_block():
    text = "intro\n```python\nx=1\n```\nmore\n```python\ndef f():\n    return 2\n```\n"
    assert "def f()" in extract_code(text)
    assert "x=1" not in extract_code(text)


def test_extract_code_without_fence():
    assert extract_code("print(1)").strip() == "print(1)"


def test_parse_json_loose_fenced():
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_loose_with_prose():
    assert parse_json_loose('Here you go: {"a": [1, 2]} hope that helps') == {"a": [1, 2]}


def test_parse_json_loose_array():
    assert parse_json_loose('[{"stdin": "1\\n"}]')[0]["stdin"] == "1\n"


def test_parse_json_loose_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_json_loose("no json at all")
