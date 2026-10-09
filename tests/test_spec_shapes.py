"""The contract extractor must survive the shapes the model actually returns.

A malformed contract crashed one program's entire migration mid-sweep, which is
a poor trade: the parsed PIC clauses already carry the information that matters,
so an odd wrapper shape should degrade rather than abort.
"""

from __future__ import annotations

from rosetta import spec
from rosetta.cobol import analyze
from pathlib import Path

PROGRAMS = Path(__file__).resolve().parent.parent / "benchmarks" / "programs"


class FakeClient:
    """Stands in for LLMClient, returning a canned contract payload."""

    def __init__(self, payload):
        self.payload = payload

    def chat_json(self, *_a, **_kw):
        return self.payload


def _contract(payload, program="checkdig.cbl"):
    prog = analyze(PROGRAMS / program)
    return spec.extract_contract(FakeClient(payload), "fake-model", prog), prog


def test_object_response_is_used():
    contract, prog = _contract(
        {
            "stdin_lines": 1,
            "stdin_fields": [{"order": 0, "name": "WS-CARD", "type": "alpha", "width": 16}],
            "stdout_description": "four lines",
        }
    )
    assert contract.stdin_fields[0]["name"] == "WS-CARD"
    assert contract.stdout_description == "four lines"


def test_bare_list_response_is_treated_as_the_field_array():
    # Observed in a real sweep: the model returned the array, not the wrapper.
    contract, _ = _contract(
        [{"order": 0, "name": "WS-CARD", "type": "alpha", "width": 16}]
    )
    assert len(contract.stdin_fields) == 1
    assert contract.stdin_fields[0]["name"] == "WS-CARD"


def test_list_wrapping_the_object_is_unwrapped():
    contract, _ = _contract(
        [{"stdin_lines": 1, "stdin_fields": [{"order": 0, "name": "WS-CARD"}]}]
    )
    assert contract.stdin_fields[0]["name"] == "WS-CARD"


def test_junk_response_degrades_to_the_parsed_pic_clauses():
    # No fields from the model at all: the run must still proceed, sized by the
    # parser's own ACCEPT count.
    contract, prog = _contract("not even json-shaped")
    assert contract.stdin_lines >= prog.accept_count
    assert contract.stdin_lines >= 1


def test_non_list_fields_value_is_ignored():
    contract, _ = _contract({"stdin_lines": 2, "stdin_fields": "WS-CARD"})
    assert contract.stdin_fields == []
    assert contract.stdin_lines == 2


def test_pic_clause_overrides_the_model_on_width():
    # WS-CARD is PIC X(16); the model claiming width 4 must not win.
    contract, _ = _contract(
        {"stdin_lines": 1, "stdin_fields": [{"order": 0, "name": "WS-CARD", "type": "alpha", "width": 4}]}
    )
    assert contract.stdin_fields[0]["width"] == 16


def test_fallback_contract_is_built_from_the_pic_clauses():
    # A truncated JSON response must not cost the whole program: the ACCEPT
    # count and PIC clauses are already parsed.
    prog = analyze(PROGRAMS / "interest.cbl")
    contract = spec.fallback_contract(prog)
    assert contract.stdin_lines == prog.accept_count == 3
    assert len(contract.stdin_fields) == 3
    assert all(f["digits"] > 0 for f in contract.stdin_fields)
    assert "static analysis" in contract.notes


def test_fallback_contract_handles_a_program_with_no_numeric_fields():
    prog = analyze(PROGRAMS / "inspectrep.cbl")
    contract = spec.fallback_contract(prog)
    assert contract.stdin_lines >= 1
    assert contract.stdin_fields
