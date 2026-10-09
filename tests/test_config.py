"""Configuration regressions.

Two facts here were wrong in the first cut and cost nothing to assert: the API
host (the original one now redirects away, so every call would have failed) and
the distillation target (Token Factory fine-tunes no Nemotron, so the job would
have been rejected). Both are the kind of thing that rots silently.
"""

from __future__ import annotations

import pytest

from rosetta import config
from rosetta.config import (
    DEFAULT_BASE_URL,
    DEFAULT_STUDENT,
    FINE_TUNABLE_STUDENTS,
    TIER_PATTERNS,
    ModelRouting,
    _pick,
    resolve_models,
)

# The Nemotron ids Token Factory actually serves, from its model catalog.
SERVED = [
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/Nemotron-3-Ultra-550b-a55b",
    "nvidia/Nemotron-3_5-Lightning",
    "meta-llama/Llama-3.1-8B-Instruct",
    "Qwen/Qwen3-30B-A3B",
]


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Keep resolution off the real cache and the developer's own env pins."""
    monkeypatch.setattr(config, "STATE_DIR", tmp_path)
    monkeypatch.setattr(config, "MODEL_CACHE", tmp_path / "models.json")
    for var in (
        "ROSETTA_MODEL_REASON",
        "ROSETTA_MODEL_FAST",
        "ROSETTA_MODEL_MID",
        "ROSETTA_MODEL_STUDENT",
    ):
        monkeypatch.delenv(var, raising=False)


def test_base_url_is_the_token_factory_host():
    # api.studio.nebius.com now 307-redirects; pointing there breaks every call.
    assert DEFAULT_BASE_URL == "https://api.tokenfactory.nebius.com/v1"
    assert "studio.nebius.com" not in DEFAULT_BASE_URL


def test_tiers_resolve_against_the_real_served_catalog():
    routing = resolve_models(served=SERVED, refresh=True)
    assert routing.reason == "nvidia/Nemotron-3-Ultra-550b-a55b"
    assert routing.fast == "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    assert routing.mid == "nvidia/nemotron-3-super-120b-a12b"


def test_every_discovered_tier_is_a_nemotron():
    routing = resolve_models(served=SERVED, refresh=True)
    for tier in (routing.reason, routing.fast, routing.mid):
        assert "nemotron" in tier.lower()


def test_student_default_is_fine_tunable_and_not_a_nemotron():
    # No Nemotron model is fine-tunable, so the student must come from the
    # fine-tunable catalog instead.
    assert DEFAULT_STUDENT in FINE_TUNABLE_STUDENTS
    for candidate in FINE_TUNABLE_STUDENTS:
        assert "nemotron" not in candidate.lower()


def test_student_is_configured_not_discovered():
    routing = resolve_models(served=SERVED, refresh=True)
    assert routing.student == DEFAULT_STUDENT

    # A Nemotron being served must never make it the fine-tuning target.
    assert routing.student not in (routing.reason, routing.fast, routing.mid)


def test_student_honours_an_explicit_pin(monkeypatch):
    monkeypatch.setenv("ROSETTA_MODEL_STUDENT", "Qwen/Qwen3-30B-A3B")
    assert resolve_models(served=SERVED, refresh=True).student == "Qwen/Qwen3-30B-A3B"


def test_env_pin_overrides_discovery(monkeypatch):
    monkeypatch.setenv("ROSETTA_MODEL_REASON", "nvidia/Nemotron-3_5-Lightning")
    assert resolve_models(served=SERVED, refresh=True).reason == (
        "nvidia/Nemotron-3_5-Lightning"
    )


def test_unresolvable_tier_fails_loudly():
    # Better to stop with a clear message than to send calls to a model that
    # does not exist and read the 404 as a transient error.
    with pytest.raises(RuntimeError, match="Could not resolve"):
        resolve_models(served=["meta-llama/Llama-3.1-8B-Instruct"], refresh=True)


def test_pick_prefers_the_higher_priority_pattern():
    # Ultra outranks Super for the reasoning tier even when both are served.
    assert _pick(SERVED, TIER_PATTERNS["reason"]) == "nvidia/Nemotron-3-Ultra-550b-a55b"


def test_routing_round_trips_through_its_dict():
    routing = ModelRouting(reason="r", fast="f", mid="m", student="s")
    assert routing.as_dict() == {"reason": "r", "fast": "f", "mid": "m", "student": "s"}
