"""Configuration and Nemotron model-tier routing."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path

STATE_DIR = Path(os.environ.get("ROSETTA_STATE_DIR", ".rosetta"))
MODEL_CACHE = STATE_DIR / "models.json"

DEFAULT_BASE_URL = "https://api.studio.nebius.com/v1"

# Tier -> ordered regex preferences used to pick a served model id.
# Highest-priority pattern that matches a served id wins. Nemotron 3 names are
# preferred; the older Llama-Nemotron generation is kept as a fallback so the
# pipeline still runs if a tier is not yet served in a given region.
TIER_PATTERNS: dict[str, list[str]] = {
    "reason": [
        r"nemotron.*3.*ultra",
        r"nemotron.*ultra",
        r"nemotron.*253b",
        r"nemotron.*3.*super",
        r"nemotron.*super",
    ],
    "mid": [
        r"nemotron.*3.*super",
        r"nemotron.*super",
        r"nemotron.*49b",
        r"nemotron.*3.*ultra",
    ],
    "fast": [
        r"nemotron.*3.*nano",
        r"nemotron.*nano",
        r"nemotron.*(8b|9b|12b)",
        r"nemotron.*super",
    ],
}


@dataclass
class ModelRouting:
    """Which Nemotron tier handles which job.

    reason -> translation + repair (needs real reasoning)
    fast   -> spec extraction + test-vector generation (high volume, cheap)
    mid    -> optional middle tier, used by the distillation comparison
    """

    reason: str
    fast: str
    mid: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class Settings:
    api_key: str
    base_url: str
    sandbox: str
    sandbox_image: str
    timeout_sec: int
    test_vectors: int
    max_repair_iters: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.environ.get("NEBIUS_API_KEY", ""),
            base_url=os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            sandbox=os.environ.get("ROSETTA_SANDBOX", "docker"),
            sandbox_image=os.environ.get("ROSETTA_SANDBOX_IMAGE", "rosetta-sandbox:latest"),
            timeout_sec=int(os.environ.get("ROSETTA_TIMEOUT_SEC", "10")),
            test_vectors=int(os.environ.get("ROSETTA_TEST_VECTORS", "40")),
            max_repair_iters=int(os.environ.get("ROSETTA_MAX_REPAIR_ITERS", "3")),
        )


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env loader so the CLI works without extra deps."""
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and val and key not in os.environ:
            os.environ[key] = val


def _pick(served: list[str], patterns: list[str]) -> str | None:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        hits = [m for m in served if rx.search(m)]
        if hits:
            # Shortest id among equal-priority hits tends to be the base model
            # rather than a quantised or speculative-decoding variant.
            return sorted(hits, key=len)[0]
    return None


def resolve_models(served: list[str] | None = None, refresh: bool = False) -> ModelRouting:
    """Resolve the three tiers.

    Order of precedence: explicit env pin -> cached resolution -> discovery from
    the served model list. Discovery keeps the project working as Nebius rotates
    model ids, instead of hard-coding strings that go stale.
    """
    env_pins = {
        "reason": os.environ.get("ROSETTA_MODEL_REASON", "").strip(),
        "fast": os.environ.get("ROSETTA_MODEL_FAST", "").strip(),
        "mid": os.environ.get("ROSETTA_MODEL_MID", "").strip(),
    }

    cached: dict[str, str] = {}
    if MODEL_CACHE.exists() and not refresh:
        try:
            cached = json.loads(MODEL_CACHE.read_text())
        except json.JSONDecodeError:
            cached = {}

    resolved: dict[str, str] = {}
    for tier in ("reason", "fast", "mid"):
        if env_pins[tier]:
            resolved[tier] = env_pins[tier]
        elif cached.get(tier) and not refresh:
            resolved[tier] = cached[tier]
        elif served:
            hit = _pick(served, TIER_PATTERNS[tier])
            if hit:
                resolved[tier] = hit

    missing = [t for t in ("reason", "fast", "mid") if t not in resolved]
    if missing:
        raise RuntimeError(
            "Could not resolve Nemotron tier(s): "
            + ", ".join(missing)
            + ". Run `rosetta models --resolve` to discover served ids, or pin them "
            "via ROSETTA_MODEL_REASON / ROSETTA_MODEL_FAST / ROSETTA_MODEL_MID."
        )

    routing = ModelRouting(**resolved)
    if served or refresh:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        MODEL_CACHE.write_text(json.dumps(routing.as_dict(), indent=2))
    return routing
