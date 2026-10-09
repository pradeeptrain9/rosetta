"""Stage 5: the repair loop.

This is where the reasoning tier earns its cost. It is handed the failing input,
what COBOL produced, what the port produced, and the semantic rules, and it
rewrites the whole file. Rewriting beats patching here: a scale bug is usually
systemic across every arithmetic site, and a diff-sized fix leaves the rest wrong.
"""

from __future__ import annotations

from .llm import LLMClient
from .models import CobolProgram, DiffResult, RepairAttempt
from .translate import SEMANTIC_RULES

_SYSTEM = (
    "You are debugging a COBOL-to-Python port against the original binary. The "
    "COBOL output is ground truth and is never wrong. You diagnose the root "
    "cause, then return the complete corrected Python file.\n\n"
    "Output format is absolute: your reply begins with ```python on the very "
    "first line and contains nothing but that one fenced file. Do your "
    "diagnosis silently. Narrating it exhausts the response budget and the "
    "file gets cut off, which is a total failure."
)

# Retry prompt: drops the semantic-rules appendix, which is generic and has been
# supplied once already, but KEEPS the COBOL source. The rules are what make the
# first prompt long enough to provoke an essay; the COBOL is the specification
# being matched, and a repair written without it regresses badly - dropping it
# produced candidates that parsed cleanly and then failed every single vector.
_COMPACT_PROMPT = """Fix this Python port so it matches the COBOL original exactly.

COBOL original (this is the specification - match it exactly):
```cobol
{cobol}
```

Current Python port:
```python
{python}
```

Failing cases:

{failures}

{strategy}

Return ONLY the complete corrected Python file in one ```python fenced block.
No analysis. No commentary. Start with ```python on the first line.
"""

_PROMPT = """The port is not behaviourally equivalent to the COBOL original.

Original COBOL:
```cobol
{cobol}
```

Current Python port:
```python
{python}
```

Failing cases ({n_failing} of {n_total} vectors failed):

{failures}

{rules}

{strategy}

Do not special-case the failing inputs - hard-coding an expected output is a
failed repair.

Return ONLY the complete corrected Python file in a single ```python fenced block.
"""

# How to repair depends on how much is broken, and getting this backwards costs
# a whole iteration. Told to "correct every site" when a single vector fails,
# the model rewrites working code and regresses: measured candidates of 39->25,
# 30->22 and 32->0 from near-passing states. Told to make a surgical change when
# most vectors fail, it patches one symptom of a systemic scale error.
_STRATEGY_SYSTEMIC = """Diagnose the root cause of each failure. Fix the cause, not
the symptom: if a quantisation is wrong in one place it is almost certainly wrong
everywhere, so correct every site that shares the defect."""

_STRATEGY_SURGICAL = """Nearly every vector already passes, so the remaining defect
is narrow and local. Make the SMALLEST change that fixes these cases. Do not
restructure, do not rename, do not "improve" anything that already works -
{n_passing} of {n_total} vectors currently match byte for byte and a rewrite that
breaks any of them is a worse answer than the file you were given. Identify the
specific expression or format that is wrong and change only that."""


def _strategy(n_failing: int, n_total: int) -> str:
    """Pick the repair strategy from the share of vectors failing."""
    if n_total and n_failing <= max(2, n_total // 10):
        return _STRATEGY_SURGICAL.format(
            n_passing=n_total - n_failing, n_total=n_total
        )
    return _STRATEGY_SYSTEMIC


def _render_failure(d: DiffResult, index: int) -> str:
    body = [f"--- failure {index} [{d.kind}] ---", f"stdin:\n{d.stdin!r}"]
    if d.kind == "STDOUT_DIFF":
        body.append(f"stdout diff (- cobol, + python):\n{d.detail}")
    else:
        body.append(f"detail:\n{d.detail}")
    return "\n".join(body)


def repair(
    client: LLMClient,
    model: str,
    prog: CobolProgram,
    python_code: str,
    failures: list[DiffResult],
    n_total: int,
    iteration: int,
    n_failing: int | None = None,
    fallback_model: str | None = None,
) -> tuple[str, RepairAttempt]:
    rendered = "\n\n".join(_render_failure(d, i + 1) for i, d in enumerate(failures))
    true_failing = n_failing if n_failing is not None else len(failures)
    patched = client.chat_code(
        model,
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _PROMPT.format(
                    cobol=prog.source,
                    python=python_code,
                    n_failing=true_failing,
                    n_total=n_total,
                    failures=rendered,
                    rules=SEMANTIC_RULES,
                    strategy=_strategy(true_failing, n_total),
                ),
            },
        ],
        retry_messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _COMPACT_PROMPT.format(
                    cobol=prog.source,
                    python=python_code,
                    failures=rendered,
                    strategy=_strategy(true_failing, n_total),
                ),
            },
        ],
        fallback_model=fallback_model,
    )
    attempt = RepairAttempt(
        iteration=iteration,
        # The TRUE failing count, not len(failures): `failures` is the small
        # representative sample shown to the model. Recording the sample size
        # here made a 34-to-4 improvement look like 2-to-4, which then got the
        # trace excluded from the distillation set as a regression.
        failures_before=true_failing,
        failures_after=-1,  # filled in by the pipeline after re-running
        failure_kinds=sorted({d.kind for d in failures}),
        diff_excerpt=rendered[:4000],
        patched_code=patched,
    )
    return patched, attempt
