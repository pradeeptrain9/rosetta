"""Test-vector responses arrive in several shapes; none may be dropped silently.

Two programs in a real sweep generated zero vectors with no warning, because the
model wrapped the array under a key the parser did not look for. The suite
shrank to boundary probes and still reported a pass rate, which overstates how
much was actually verified.
"""

from __future__ import annotations

from rosetta.testgen import _as_vector_list, llm_vectors
from rosetta.models import IOContract

CONTRACT = IOContract(
    stdin_lines=1,
    stdin_fields=[
        {"order": 0, "name": "WS-AMT", "type": "numeric", "digits": 8,
         "scale": 0, "signed": False, "width": 0, "domain": ""}
    ],
)


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def chat_json(self, *_a, **_kw):
        return self.payload


def test_plain_array():
    assert len(_as_vector_list([{"stdin": "1\n"}, {"stdin": "2\n"}])) == 2


def test_wrapped_under_the_documented_key():
    assert len(_as_vector_list({"vectors": [{"stdin": "1\n"}]})) == 1


def test_wrapped_under_an_undocumented_key():
    # The model picks its own key; any list of entries should be found.
    assert len(_as_vector_list({"test_cases": [{"stdin": "1\n"}, {"stdin": "2\n"}]})) == 2


def test_object_keyed_by_index():
    assert len(_as_vector_list({"1": {"stdin": "a\n"}, "2": {"stdin": "b\n"}})) == 2


def test_single_unwrapped_vector():
    assert _as_vector_list({"stdin": "9\n", "note": "x"}) == [{"stdin": "9\n", "note": "x"}]


def test_unusable_shapes_yield_nothing():
    assert _as_vector_list("nonsense") == []
    assert _as_vector_list(42) == []
    assert _as_vector_list({}) == []


def test_bare_string_list_is_accepted_as_stdin():
    vectors = llm_vectors(FakeClient(["12345678", "0"]), "m", "SRC", CONTRACT, n=2)
    assert [v.stdin for v in vectors] == ["12345678\n", "0\n"]


def test_newline_is_appended_when_missing():
    vectors = llm_vectors(FakeClient([{"stdin": "42"}]), "m", "SRC", CONTRACT, n=1)
    assert vectors[0].stdin == "42\n"


def test_empty_result_is_reported_not_swallowed():
    seen: list[str] = []
    vectors = llm_vectors(
        FakeClient({"unexpected": "shape"}), "m", "SRC", CONTRACT, n=5,
        log=seen.append,
    )
    assert vectors == []
    assert any("warn" in m for m in seen), "an empty suite must be announced"


def test_recognised_shape_does_not_warn():
    seen: list[str] = []
    vectors = llm_vectors(
        FakeClient({"cases": [{"stdin": "1\n"}]}), "m", "SRC", CONTRACT, n=1,
        log=seen.append,
    )
    assert len(vectors) == 1
    assert not seen


def test_entry_without_a_stdin_key_is_dropped_and_reported():
    # Observed live: entries lacking "stdin" became "" (a valid boundary probe),
    # so they counted as usable, silenced the warning, and then collapsed to one
    # vector in the dedup.
    seen: list[str] = []
    vectors = llm_vectors(
        FakeClient([{"note": "no stdin key"}, {"note": "nor here"}]),
        "m", "SRC", CONTRACT, n=2, log=seen.append,
    )
    assert vectors == []
    assert any("warn" in m for m in seen)


def test_an_explicitly_empty_stdin_is_kept():
    # The empty line is a real input COBOL treats as zero.
    vectors = llm_vectors(FakeClient([{"stdin": ""}]), "m", "SRC", CONTRACT, n=1)
    assert len(vectors) == 1
    assert vectors[0].stdin == ""


def test_generation_that_only_duplicates_boundary_probes_is_reported():
    from rosetta.testgen import boundary_vectors, build_suite

    probes = boundary_vectors(CONTRACT, cap=20)
    dupes = [{"stdin": v.stdin} for v in probes]

    seen: list[str] = []
    suite = build_suite(
        FakeClient(dupes), "m", "SRC", CONTRACT, target=40, log=seen.append
    )
    assert len(suite) == len(probes)
    assert any("duplicated" in m for m in seen), "a suite that did not grow must say so"
