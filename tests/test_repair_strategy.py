"""The repair instruction must match the scale of the damage.

Repairs launched from a near-passing state regressed repeatedly in real runs
(39->25, 30->22, 32->0) because the prompt told the model to correct every site
that shared the defect. That is right when most vectors fail and destructive
when one does.
"""

from __future__ import annotations

from rosetta.repair import _STRATEGY_SYSTEMIC, _strategy


def test_most_vectors_failing_gets_the_systemic_instruction():
    assert _strategy(34, 40) == _STRATEGY_SYSTEMIC
    assert _strategy(40, 40) == _STRATEGY_SYSTEMIC


def test_a_single_failure_gets_the_surgical_instruction():
    s = _strategy(1, 40)
    assert s != _STRATEGY_SYSTEMIC
    assert "SMALLEST change" in s
    assert "39 of 40" in s


def test_the_surgical_threshold_is_proportional():
    # 10% or fewer failing is surgical; more is systemic.
    assert _strategy(4, 40) != _STRATEGY_SYSTEMIC
    assert _strategy(5, 40) == _STRATEGY_SYSTEMIC


def test_tiny_suites_still_allow_a_surgical_repair():
    # With a floor of 2, an 8-vector suite with one failure is still local.
    assert _strategy(1, 8) != _STRATEGY_SYSTEMIC
    assert _strategy(2, 8) != _STRATEGY_SYSTEMIC
    assert _strategy(6, 8) == _STRATEGY_SYSTEMIC


def test_zero_total_does_not_divide_by_zero():
    assert _strategy(0, 0) == _STRATEGY_SYSTEMIC
