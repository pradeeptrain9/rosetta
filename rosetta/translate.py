"""Stage 2: COBOL -> Python translation on the reasoning tier.

The prompt is deliberately specific about the semantics that actually break
naive translations: fixed-point scale, truncation vs ROUNDED, and DISPLAY
formatting widths. The model is told it does not need to be right first time -
the differential harness will tell it exactly where it was wrong.
"""

from __future__ import annotations

from .cobol import brief
from .llm import LLMClient, extract_code
from .models import CobolProgram, IOContract

_SYSTEM = (
    "You are a compiler engineer who ports COBOL to Python for regulated "
    "systems. Behavioural equivalence is the only acceptance criterion: byte "
    "identical stdout for identical stdin. Idiomatic Python is worthless if it "
    "changes a single digit. You output one complete Python file and nothing else."
)

SEMANTIC_RULES = """Semantic rules you must follow:

1. FIXED POINT, NEVER FLOAT. Every COBOL numeric field is a scaled integer.
   Use `decimal.Decimal` and set a wide context (`getcontext().prec = 40`).
   Never use `float`, `round()`, or `/` on money. A field with PIC S9(7)V99
   holds a Decimal quantized to exactly 2 decimal places.

2. TRUNCATION IS THE DEFAULT. `COMPUTE X = A * B` stores into X's picture by
   TRUNCATING toward zero, not rounding. Only `ROUNDED` rounds, and it rounds
   half away from zero (ROUND_HALF_UP), not banker's rounding.
     plain:   value.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
     ROUNDED: value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
   `DIVIDE` and `/` truncate the same way. Compute intermediates at full
   precision, then quantize once at the store into the target field.

3. SIZE IS REAL. A PIC 9(5) field cannot hold 123456; the high-order digit is
   silently lost unless ON SIZE ERROR is present. Model this by taking the
   value modulo 10**digits and re-applying the sign.

4. DISPLAY WRITES EXACT BYTES. One DISPLAY is one line on stdout.
   - PIC X(n): left justified, space padded to exactly n characters.
   - PIC 9(n): zero padded to exactly n digits, no sign, no separators.
   - Edited pictures (Z, *, comma, period, +, -, CR, DB, currency) must be
     reproduced character for character, including suppressed leading zeros
     becoming spaces and the trailing-sign position.
   - Literals concatenated in a DISPLAY keep their exact spacing.

5. MOVE FOLLOWS COBOL RULES. numeric -> numeric aligns on the decimal point and
   truncates both ends. alphanumeric -> alphanumeric is left justified and
   space padded or truncated on the right. Group moves copy bytes.

6. CONTROL FLOW. A paragraph becomes a function. PERFORM <para> calls it.
   PERFORM ... VARYING becomes a loop with the same inclusive bounds and the
   same post-loop value of the control variable. PERFORM UNTIL tests before
   the body (TEST BEFORE is the default). Level-88 condition names become
   predicates. Preserve fall-through between consecutive paragraphs exactly as
   COBOL does when control reaches the end of one paragraph.

7. INPUT. Each ACCEPT consumes one line from stdin. Read with
   `sys.stdin.readline()`, strip the trailing newline only, and convert
   according to the receiving field's picture. A short or non-numeric line that
   COBOL would treat as zero must become zero, not an exception.

8. TERMINATION. STOP RUN exits 0. GOBACK returns. Do not print tracebacks on
   malformed input unless the COBOL program would also abort.
"""

_PROMPT = """Port this COBOL program to a single self-contained Python 3 file.

Static analysis:
{brief}

I/O contract:
  stdin lines: {stdin_lines}
  stdin fields: {stdin_fields}
  stdout: {stdout_desc}
  notes: {notes}

{rules}

Output requirements:
- One file, standard library only.
- Keep the original paragraph names as function names (lowercased, hyphens to
  underscores) so a reviewer can diff the two side by side.
- Put a short comment above any line where you made a semantics judgement call.
- End with `if __name__ == "__main__": main()`.
- Return ONLY the Python code in a single ```python fenced block.

COBOL source:
```cobol
{source}
```
"""


def translate(
    client: LLMClient,
    model: str,
    prog: CobolProgram,
    contract: IOContract,
) -> str:
    fields_desc = (
        "\n    ".join(
            f"[{f['order']}] {f['name']} {f['type']} digits={f['digits']} "
            f"scale={f['scale']} signed={f['signed']} width={f['width']} "
            f"domain={f['domain']!r}"
            for f in contract.stdin_fields
        )
        or "none"
    )
    text = client.chat(
        model,
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _PROMPT.format(
                    brief=brief(prog),
                    stdin_lines=contract.stdin_lines,
                    stdin_fields=fields_desc,
                    stdout_desc=contract.stdout_description or "see source",
                    notes=contract.notes or "none",
                    rules=SEMANTIC_RULES,
                    source=prog.source,
                ),
            },
        ],
        max_tokens=16384,
    )
    return extract_code(text)
