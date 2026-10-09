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

# Retry prompt: same task, no semantic-rules appendix and no COBOL source. The
# model has seen those once already; what makes it narrate instead of answering
# is the sheer length of the first prompt.
_COMPACT_PROMPT = """Fix this Python port so it matches the COBOL original exactly.

Current Python port:
```python
{python}
```

Failing cases:

{failures}

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

Diagnose the root cause of each failure. Fix the cause, not the symptom: if a
quantisation is wrong in one place it is probably wrong everywhere, so correct
every site. Do not special-case the failing inputs - hard-coding an expected
output is a failed repair.

Return ONLY the complete corrected Python file in a single ```python fenced block.
"""


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
) -> tuple[str, RepairAttempt]:
    rendered = "\n\n".join(_render_failure(d, i + 1) for i, d in enumerate(failures))
    patched = client.chat_code(
        model,
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _PROMPT.format(
                    cobol=prog.source,
                    python=python_code,
                    n_failing=n_failing if n_failing is not None else len(failures),
                    n_total=n_total,
                    failures=rendered,
                    rules=SEMANTIC_RULES,
                ),
            },
        ],
        retry_messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _COMPACT_PROMPT.format(
                    python=python_code, failures=rendered
                ),
            },
        ],
    )
    attempt = RepairAttempt(
        iteration=iteration,
        # The TRUE failing count, not len(failures): `failures` is the small
        # representative sample shown to the model. Recording the sample size
        # here made a 34-to-4 improvement look like 2-to-4, which then got the
        # trace excluded from the distillation set as a regression.
        failures_before=n_failing if n_failing is not None else len(failures),
        failures_after=-1,  # filled in by the pipeline after re-running
        failure_kinds=sorted({d.kind for d in failures}),
        diff_excerpt=rendered[:4000],
        patched_code=patched,
    )
    return patched, attempt
