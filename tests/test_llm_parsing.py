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


def test_extract_code_rejects_echoed_cobol_and_picks_the_python_block():
    # The model sometimes restates the source; the COBOL fence can be the
    # LARGEST block in the response, so size alone picks the wrong one.
    text = (
        "Here is the original:\n"
        "```cobol\n"
        'DISPLAY "RAW   [" WS-VAL "]"\n'
        "           MOVE WS-VAL TO WS-LEAD\n"
        "           MOVE WS-VAL TO WS-TRAIL\n"
        "           MOVE WS-VAL TO WS-ED-MINUS\n"
        "```\n"
        "And the port:\n"
        "```python\n"
        "import sys\n"
        "print(1)\n"
        "```\n"
    )
    out = extract_code(text)
    assert "import sys" in out
    assert "DISPLAY" not in out


def test_extract_code_prefers_the_longest_parseable_python_block():
    text = (
        "```python\nx = 1\n```\n"
        "```python\nimport sys\n\n\ndef main():\n    return 2\n```\n"
    )
    assert "def main" in extract_code(text)


def test_extract_code_skips_a_truncated_block_for_a_valid_one():
    # A half-written function is not a usable file even if it is longer.
    text = (
        "```python\ndef broken(:\n    this is not python at all ((\n```\n"
        "```python\nprint('ok')\n```\n"
    )
    assert extract_code(text).strip() == "print('ok')"


def test_extract_code_raises_when_nothing_parses():
    with pytest.raises(ValueError, match="no parseable Python"):
        extract_code("I cannot help with that.\n```cobol\nMOVE A TO B\n```")


def test_extract_code_accepts_an_unfenced_python_response():
    assert "print" in extract_code("print('hello')")
