"""Output comparison and mismatch classification.

Equivalence here means: identical stdout after newline normalisation, and the
same success/failure disposition. Trailing-whitespace normalisation is applied
because COBOL DISPLAY pads records to the record length and a shell redirect
would strip it anyway; everything else is compared byte for byte.
"""

from __future__ import annotations

import difflib

from .models import DiffResult, RunResult, TestVector


def normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def compare(vec: TestVector, ref: RunResult, got: RunResult) -> DiffResult:
    if ref.timed_out:
        return DiffResult(vec.vid, False, "REF_CRASH", "reference timed out", vec.stdin)
    if got.timed_out:
        return DiffResult(vec.vid, False, "TIMEOUT", "migrated program timed out", vec.stdin)
    if got.exit_code < 0:
        return DiffResult(vec.vid, False, "PY_CRASH", got.stderr[-1500:], vec.stdin)

    ref_out, got_out = normalize(ref.stdout), normalize(got.stdout)

    # A Python traceback is a crash even when the exit code looks ordinary.
    if "Traceback (most recent call last)" in got.stderr:
        return DiffResult(vec.vid, False, "PY_CRASH", got.stderr[-1500:], vec.stdin)

    if ref_out == got_out and ref.exit_code == got.exit_code:
        return DiffResult(vec.vid, True, "EQUAL", "", vec.stdin)

    if ref_out != got_out:
        return DiffResult(vec.vid, False, "STDOUT_DIFF", unified(ref_out, got_out), vec.stdin)

    return DiffResult(
        vec.vid,
        False,
        "EXIT_DIFF",
        f"reference exit {ref.exit_code}, migrated exit {got.exit_code}",
        vec.stdin,
    )


def unified(expected: str, actual: str, context: int = 2) -> str:
    diff = difflib.unified_diff(
        expected.split("\n"),
        actual.split("\n"),
        fromfile="cobol",
        tofile="python",
        lineterm="",
        n=context,
    )
    return "\n".join(list(diff)[:60])


def representative_failures(diffs: list[DiffResult], per_kind: int = 2) -> list[DiffResult]:
    """Pick a small, diverse failure set for the repair prompt.

    Feeding every failure wastes context and biases the model toward whichever
    bug happens to be most frequent; one or two of each kind is more useful.
    """
    buckets: dict[str, list[DiffResult]] = {}
    for d in diffs:
        if d.equal:
            continue
        buckets.setdefault(d.kind, []).append(d)
    # Crashes first: they usually mask the subtler numeric diffs behind them.
    order = ["PY_CRASH", "TIMEOUT", "STDOUT_DIFF", "EXIT_DIFF", "REF_CRASH"]
    picked: list[DiffResult] = []
    for kind in order:
        picked.extend(buckets.get(kind, [])[:per_kind])
    for kind, items in buckets.items():
        if kind not in order:
            picked.extend(items[:per_kind])
    return picked
