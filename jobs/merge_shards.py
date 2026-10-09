"""Merge per-shard result files into one report after a Serverless Jobs sweep."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rosetta.models import MigrationResult  # noqa: E402
from rosetta.report import to_markdown  # noqa: E402


def main(out_dir: str = "out") -> int:
    out = Path(out_dir)
    rows: list[dict] = []
    for shard in sorted(out.glob("shard-*.json")):
        rows.extend(json.loads(shard.read_text()))
    if not rows:
        print(f"no shard-*.json under {out}", file=sys.stderr)
        return 1

    results = [
        MigrationResult(
            program_id=r["program_id"],
            path=r["path"],
            loc=r["loc"],
            equivalent=r["equivalent"],
            vectors_total=r["vectors_total"],
            vectors_passed=r["vectors_passed"],
            repair_iterations=r["repair_iterations"],
            python_code="",
            token_usage=r.get("token_usage", {}),
            error=r.get("error"),
        )
        for r in rows
    ]
    md = to_markdown(results, title="Rosetta equivalence report (sharded sweep)")
    (out / "report.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
