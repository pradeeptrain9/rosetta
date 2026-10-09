"""Stage 1: derive the program's I/O contract.

The fast Nemotron tier reads the source and reports which value each ACCEPT
consumes. Parsed facts from cobol.py override the model where they disagree -
the ACCEPT count in particular is never taken from the model.
"""

from __future__ import annotations

from .cobol import brief
from .llm import LLMClient
from .models import CobolProgram, IOContract

_SYSTEM = (
    "You are a COBOL analyst. You read COBOL source and report its runtime I/O "
    "contract as strict JSON. You never guess: if a value's domain is not "
    "determinable from the source, say so in the notes field."
)

_PROMPT = """Analyse this COBOL program and describe what it reads from stdin and writes to stdout.

Static analysis (authoritative - do not contradict it):
{brief}

Source:
```cobol
{source}
```

Return ONLY a JSON object with this shape:

{{
  "stdin_lines": <int: how many lines the program reads via ACCEPT>,
  "stdin_fields": [
    {{
      "order": <int, 0-based, matching ACCEPT execution order>,
      "name": "<COBOL field name the ACCEPT moves into>",
      "type": "numeric" | "alpha",
      "digits": <int total digits, 0 for alpha>,
      "scale": <int digits after the implied decimal point>,
      "signed": <bool>,
      "width": <int fixed width for alpha, else 0>,
      "domain": "<short note on valid values, e.g. '1-4 selects a branch'>"
    }}
  ],
  "stdout_description": "<one or two sentences on the exact output format>",
  "reads_files": <bool>,
  "notes": "<anything that would make behaviour non-deterministic: dates, random, file I/O>"
}}

If an ACCEPT sits inside a loop whose trip count depends on input, set
stdin_lines to the count for a single typical pass and explain in notes.
"""


def fallback_contract(prog: CobolProgram) -> IOContract:
    """Build a contract from the static analysis alone.

    The model's contract is a convenience, not a requirement: the ACCEPT count
    and the PIC clauses are already parsed, and losing a whole program because a
    JSON response was truncated is a far worse outcome than probing it with a
    generic field shape. Vector generation still sees the real source.
    """
    numeric = [f for f in prog.fields if f.digits]
    digits = max((f.digits for f in numeric), default=8)
    scale = max((f.scale for f in numeric), default=0)
    signed = any(f.signed for f in numeric)
    lines = max(prog.accept_count, 1)

    return IOContract(
        stdin_lines=lines,
        stdin_fields=[
            {
                "order": i,
                "name": f"ACCEPT-{i + 1}",
                "type": "numeric",
                "digits": digits,
                "scale": scale,
                "signed": signed,
                "width": 0,
                "domain": "inferred from the program's PIC clauses",
            }
            for i in range(lines)
        ],
        stdout_description=f"{prog.display_count} DISPLAY statement(s)",
        reads_files=bool(prog.file_selects),
        notes="contract inferred from static analysis; the model's response was unusable",
    )


def extract_contract(client: LLMClient, model: str, prog: CobolProgram) -> IOContract:
    data = client.chat_json(
        model,
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _PROMPT.format(brief=brief(prog), source=prog.source),
            },
        ],
        max_tokens=8192,
    )

    # The model is asked for an object but sometimes returns just the field
    # array, or a single-element list wrapping the object. Normalising here is
    # cheaper than a retry, and an unusable shape must not crash the program's
    # whole migration.
    if isinstance(data, list):
        wrapper = next((x for x in data if isinstance(x, dict) and "stdin_fields" in x), None)
        data = wrapper if wrapper is not None else {"stdin_fields": data}
    if not isinstance(data, dict):
        data = {}

    fields = data.get("stdin_fields") or []
    if not isinstance(fields, list):
        fields = []
    # Normalise and backfill from the PIC clauses we parsed ourselves.
    by_name = {f.name: f for f in prog.fields}
    clean: list[dict] = []
    for i, f in enumerate(fields):
        name = str(f.get("name", "")).upper()
        parsed = by_name.get(name)
        entry = {
            "order": int(f.get("order", i)),
            "name": name or f"FIELD-{i}",
            "type": f.get("type", "numeric"),
            "digits": int(f.get("digits") or 0),
            "scale": int(f.get("scale") or 0),
            "signed": bool(f.get("signed")),
            "width": int(f.get("width") or 0),
            "domain": str(f.get("domain", "")),
        }
        if parsed is not None:
            # PIC clause wins over the model's reading of it.
            if parsed.alpha_len:
                entry.update(type="alpha", width=parsed.alpha_len, digits=0, scale=0)
            elif parsed.digits:
                entry.update(
                    type="numeric",
                    digits=parsed.digits,
                    scale=parsed.scale,
                    signed=parsed.signed,
                )
        clean.append(entry)
    clean.sort(key=lambda e: e["order"])

    model_lines = int(data.get("stdin_lines") or 0)
    # The parser counts ACCEPT *statements*; one inside a loop consumes many
    # lines, so the statement count is a floor rather than the answer. Take the
    # largest of the three estimates: feeding a program more lines than it reads
    # is harmless (both binaries get the same stdin), while feeding it too few
    # starves it of input and collapses coverage to the EOF path.
    stdin_lines = max(prog.accept_count, model_lines, len(clean))

    return IOContract(
        stdin_lines=stdin_lines,
        stdin_fields=clean,
        stdout_description=str(data.get("stdout_description", "")),
        reads_files=bool(data.get("reads_files")) or bool(prog.file_selects),
        notes=str(data.get("notes", "")),
    )
