from __future__ import annotations

from rosetta.differ import compare, representative_failures
from rosetta.models import RunResult, TestVector


def _rr(stdout="", stderr="", code=0, timed_out=False):
    return RunResult(stdout=stdout, stderr=stderr, exit_code=code,
                     duration_ms=1, timed_out=timed_out)


VEC = TestVector.make("1\n", "boundary")


def test_equal_outputs():
    d = compare(VEC, _rr("BALANCE 100.00\n"), _rr("BALANCE 100.00\n"))
    assert d.equal and d.kind == "EQUAL"


def test_trailing_whitespace_is_not_a_difference():
    assert compare(VEC, _rr("X   \n"), _rr("X\n")).equal


def test_single_digit_difference_fails():
    d = compare(VEC, _rr("TOTAL 100.00\n"), _rr("TOTAL 100.01\n"))
    assert not d.equal and d.kind == "STDOUT_DIFF"
    assert "100.01" in d.detail


def test_traceback_is_a_crash_even_with_exit_zero():
    d = compare(VEC, _rr("X\n"), _rr("X\n", "Traceback (most recent call last):\n", 0))
    assert d.kind == "PY_CRASH"


def test_timeout_classified():
    assert compare(VEC, _rr("X\n"), _rr(timed_out=True)).kind == "TIMEOUT"


def test_exit_code_difference():
    d = compare(VEC, _rr("X\n", code=0), _rr("X\n", code=3))
    assert not d.equal and d.kind == "EXIT_DIFF"


def test_representative_failures_puts_crashes_first_and_caps_per_kind():
    from rosetta.models import DiffResult

    diffs = [
        DiffResult("a", False, "STDOUT_DIFF", "d1"),
        DiffResult("b", False, "STDOUT_DIFF", "d2"),
        DiffResult("c", False, "STDOUT_DIFF", "d3"),
        DiffResult("d", False, "PY_CRASH", "boom"),
        DiffResult("e", True, "EQUAL", ""),
    ]
    picked = representative_failures(diffs, per_kind=2)
    assert picked[0].kind == "PY_CRASH"
    assert len(picked) == 3
    assert all(not p.equal for p in picked)
