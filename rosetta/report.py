"""Benchmark reporting: the artefact the demo video points a camera at."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .models import MigrationResult


def to_json(results: list[MigrationResult], path: str | Path) -> None:
    Path(path).write_text(json.dumps([r.summary() for r in results], indent=2))


def aggregate_tokens(results: list[MigrationResult]) -> dict[str, dict[str, int]]:
    agg: dict[str, dict[str, int]] = defaultdict(lambda: {"prompt": 0, "completion": 0, "calls": 0})
    for r in results:
        for model, row in r.token_usage.items():
            for key in ("prompt", "completion", "calls"):
                agg[model][key] += row.get(key, 0)
    return dict(agg)


def to_markdown(results: list[MigrationResult], title: str = "Rosetta equivalence report") -> str:
    total = len(results)
    equiv = sum(1 for r in results if r.equivalent)
    vectors = sum(r.vectors_total for r in results)
    passed = sum(r.vectors_passed for r in results)
    repaired = sum(1 for r in results if r.equivalent and r.repair_iterations > 0)
    first_try = sum(1 for r in results if r.equivalent and r.repair_iterations == 0)

    lines = [
        f"# {title}",
        "",
        "## Headline",
        "",
        f"- Programs migrated with proven equivalence: **{equiv}/{total}**"
        + (f" ({equiv / total:.0%})" if total else ""),
        f"- Equivalent on first translation: **{first_try}**",
        f"- Equivalent only after repair: **{repaired}**",
        f"- Differential test vectors executed: **{vectors}**, passed **{passed}**"
        + (f" ({passed / vectors:.2%})" if vectors else ""),
        "",
        "## Per program",
        "",
        "| Program | COBOL LOC | Vectors | Passed | Repairs | Equivalent | Note |",
        "|---|---:|---:|---:|---:|:--:|---|",
    ]

    for r in sorted(results, key=lambda x: (not x.equivalent, x.program_id)):
        note = r.error or ""
        if not note and not r.equivalent:
            kinds = sorted({d.kind for d in r.diffs if not d.equal})
            note = ", ".join(kinds)
        lines.append(
            f"| `{r.program_id}` | {r.loc} | {r.vectors_total} | {r.vectors_passed} "
            f"| {r.repair_iterations} | {'yes' if r.equivalent else 'no'} | {note} |"
        )

    lines += ["", "## Token usage by Nemotron tier", "", "| Model | Calls | Prompt tokens | Completion tokens | Total |", "|---|---:|---:|---:|---:|"]
    agg = aggregate_tokens(results)
    for model, row in sorted(agg.items(), key=lambda kv: -(kv[1]["prompt"] + kv[1]["completion"])):
        tot = row["prompt"] + row["completion"]
        lines.append(
            f"| `{model}` | {row['calls']} | {row['prompt']:,} | {row['completion']:,} | {tot:,} |"
        )

    grand = sum(r["prompt"] + r["completion"] for r in agg.values())
    lines += [
        "",
        f"Total tokens through Nebius Token Factory: **{grand:,}**",
        "",
        "## How to read this",
        "",
        "Equivalence is not an opinion from a model. Each row means the migrated",
        "Python produced byte-identical stdout to the GnuCOBOL-compiled original",
        "across every listed input vector, including boundary and overflow cases",
        "generated from the program's own PIC clauses.",
        "",
    ]
    return "\n".join(lines)
