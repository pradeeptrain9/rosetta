"""Stage 3: test-vector generation.

Two sources, deliberately. Deterministic boundary probes derived from the PIC
clauses catch the failures that actually occur in COBOL ports (scale, overflow,
sign, non-numeric input), and cost nothing. The fast Nemotron tier then adds
semantic vectors that exercise branch logic a picture clause cannot reveal.
Volume here is cheap, which is the whole reason the fast tier exists.
"""

from __future__ import annotations

import random

from typing import Callable

from .llm import LLMClient
from .models import IOContract, TestVector

_SYSTEM = (
    "You generate test inputs for COBOL programs. You aim for branch coverage "
    "and for inputs a careless port would get wrong. You return strict JSON."
)

_PROMPT = """Generate {n} stdin test inputs for this COBOL program.

Each input must be exactly {lines} line(s), one line per ACCEPT, in this order:
{fields}

Program behaviour: {stdout_desc}

Source:
```cobol
{source}
```

Aim for: every branch taken at least once, values at field capacity, values
that overflow the field, zero, negative where the field is signed, and inputs
that are not valid numbers at all.

Return ONLY a JSON array of objects:
[{{"stdin": "line1\\nline2\\n", "note": "what this probes"}}]
"""


def _numeric_probes(digits: int, scale: int, signed: bool) -> list[str]:
    d = max(digits, 1)
    full = "9" * d
    mid = ("1" + "0" * (d - 1)) if d > 1 else "5"
    probes = ["0", "1", mid, full, "9" * (d + 1)]  # last one overflows the field
    if signed:
        probes += ["-1", f"-{mid}"]
    if scale:
        probes.append(("0" * (d - scale) if d > scale else "0") + "5" * scale)
    probes += ["", "ABC", " "]  # COBOL treats these as zero; naive ports crash
    seen, out = set(), []
    for p in probes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _alpha_probes(width: int) -> list[str]:
    w = max(width, 1)
    return ["", "A", "A" * w, "A" * (w + 3), " " * w, "A B", "0"]


def _field_probes(field: dict) -> list[str]:
    if field.get("type") == "alpha":
        return _alpha_probes(int(field.get("width") or 1))
    return _numeric_probes(
        int(field.get("digits") or 1),
        int(field.get("scale") or 0),
        bool(field.get("signed")),
    )


def boundary_vectors(contract: IOContract, cap: int = 60) -> list[TestVector]:
    """One-field-at-a-time variation around a baseline, plus random combinations.

    Full cartesian product explodes; varying one field at a time localises the
    blame when a vector fails, which makes the repair prompt far more pointed.
    """
    fields = contract.stdin_fields
    if not fields:
        return [TestVector.make("", "boundary", "no stdin")]

    # An ACCEPT in a loop reads more lines than the contract lists fields for
    # (one statement, one field, eight reads). Cycle the known field specs to
    # cover the full line count, otherwise every vector is short and the
    # program only ever gets tested down its EOF path.
    if contract.stdin_lines > len(fields):
        fields = [fields[i % len(fields)] for i in range(contract.stdin_lines)]

    probe_sets = [_field_probes(f) for f in fields]
    baseline = [ps[1] if len(ps) > 1 else ps[0] for ps in probe_sets]

    vectors: list[TestVector] = []
    seen: set[str] = set()

    def push(values: list[str], note: str) -> None:
        stdin = "".join(v + "\n" for v in values)
        if stdin in seen:
            return
        seen.add(stdin)
        vectors.append(TestVector.make(stdin, "boundary", note))

    push(baseline, "baseline")
    for i, probes in enumerate(probe_sets):
        for probe in probes:
            vals = list(baseline)
            vals[i] = probe
            push(vals, f"{fields[i]['name']}={probe!r}")

    rng = random.Random(1729)  # fixed seed: vectors must be reproducible
    while len(vectors) < cap:
        before = len(vectors)
        push([rng.choice(ps) for ps in probe_sets], "random combination")
        if len(vectors) == before and len(seen) >= _max_combos(probe_sets):
            break  # probe space exhausted

    return vectors[:cap]


def _max_combos(probe_sets: list[list[str]]) -> int:
    total = 1
    for ps in probe_sets:
        total *= len(ps)
        if total > 100_000:
            return 100_000
    return total


def llm_vectors(
    client: LLMClient,
    model: str,
    source: str,
    contract: IOContract,
    n: int = 20,
    log: Callable[[str], None] = lambda _m: None,
) -> list[TestVector]:
    fields_desc = (
        "\n".join(
            f"  line {f['order'] + 1}: {f['name']} ({f['type']}, digits={f['digits']}, "
            f"scale={f['scale']}, signed={f['signed']}, width={f['width']}) "
            f"domain: {f['domain']}"
            for f in contract.stdin_fields
        )
        or "  (no stdin)"
    )
    try:
        data = client.chat_json(
            model,
            [
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": _PROMPT.format(
                        n=n,
                        lines=contract.stdin_lines,
                        fields=fields_desc,
                        stdout_desc=contract.stdout_description or "see source",
                        source=source,
                    ),
                },
            ],
            temperature=0.7,  # diversity matters more than determinism here
            # Headroom matters here: 20 vectors with notes has been measured at
            # ~3.9k completion tokens, so a 4k cap sat right on the edge and
            # intermittently returned nothing at all.
            max_tokens=8192,
        )
    except (ValueError, RuntimeError) as exc:
        # Boundary vectors alone are still a valid run, but it is a much weaker
        # claim, so say so rather than quietly proving equivalence over a
        # fraction of the intended suite.
        log(f"[warn] generated vectors unavailable, boundary probes only: {exc}")
        return []

    items = _as_vector_list(data)
    out: list[TestVector] = []
    for item in items:
        if isinstance(item, str):
            # Some responses are a bare list of input strings.
            stdin, note = item, ""
        elif isinstance(item, dict):
            stdin, note = str(item.get("stdin", "")), str(item.get("note", ""))
        else:
            continue
        if stdin and not stdin.endswith("\n"):
            stdin += "\n"
        out.append(TestVector.make(stdin, "llm", note))

    if not out:
        # The call succeeded but yielded nothing usable. Silence here is how a
        # suite quietly shrinks to boundary probes only, and a thin suite proves
        # equivalence over far less than it appears to.
        log(
            "[warn] test-vector response had no usable entries "
            f"(top level was {type(data).__name__}); boundary probes only"
        )
    return out


def _as_vector_list(data: object) -> list:
    """Find the list of vectors in whatever shape came back.

    Asked for a JSON array, the model variously returns the array, an object
    wrapping it under some key of its choosing, or an object keyed by index.
    Hunting for the list is far cheaper than another round trip.
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("vectors", "test_inputs", "inputs", "cases", "tests", "data"):
        val = data.get(key)
        if isinstance(val, list):
            return val

    # Any list-of-entries value will do, whatever it is called.
    for val in data.values():
        if isinstance(val, list) and val and isinstance(val[0], (dict, str)):
            return val

    # An object keyed by index, e.g. {"1": {...}, "2": {...}}.
    if data and all(isinstance(v, dict) for v in data.values()):
        return list(data.values())

    # A single vector returned unwrapped.
    if "stdin" in data:
        return [data]
    return []


def build_suite(
    client: LLMClient,
    fast_model: str,
    source: str,
    contract: IOContract,
    target: int = 40,
    log: Callable[[str], None] = lambda _m: None,
) -> list[TestVector]:
    """Boundary probes first, topped up with model-generated vectors."""
    boundary = boundary_vectors(contract, cap=max(target // 2, 10))
    want = max(target - len(boundary), 0)
    extra = (
        llm_vectors(client, fast_model, source, contract, n=want, log=log)
        if want
        else []
    )

    merged: dict[str, TestVector] = {v.stdin: v for v in boundary}
    for v in extra:
        merged.setdefault(v.stdin, v)
    return list(merged.values())[:target]
