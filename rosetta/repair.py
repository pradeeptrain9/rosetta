"""Stage 5: the repair loop.

This is where the reasoning tier earns its cost. It is handed the failing input,
what COBOL produced, what the port produced, and the semantic rules, and it
rewrites the whole file. Rewriting beats patching here: a scale bug is usually
systemic across every arithmetic site, and a diff-sized fix leaves the rest wrong.
"""

from __future__ import annotations

from .llm import LLMClient, extract_code
from .models import CobolProgram, DiffResult, RepairAttempt
from .translate import SEMANTIC_RULES

_SYSTEM = (
    "You are debugging a COBOL-to-Python port against the original binary. The "
    "COBOL output is ground truth and is never wrong. You diagnose the root "
    "cause, then return the complete corrected Python file."
)

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
) -> tuple[str, RepairAttempt]:
    rendered = "\n\n".join(_render_failure(d, i + 1) for i, d in enumerate(failures))
    text = client.chat(
        model,
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _PROMPT.format(
                    cobol=prog.source,
                    python=python_code,
                    n_failing=len(failures),
                    n_total=n_total,
                    failures=rendered,
                    rules=SEMANTIC_RULES,
                ),
            },
        ],
        max_tokens=16384,
    )
    patched = extract_code(text)
    attempt = RepairAttempt(
        iteration=iteration,
        failures_before=len(failures),
        failures_after=-1,  # filled in by the pipeline after re-running
        failure_kinds=sorted({d.kind for d in failures}),
        diff_excerpt=rendered[:4000],
        patched_code=patched,
    )
    return patched, attempt
