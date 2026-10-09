"""Regenerate the aggregate report from whatever is in out/.

`rosetta bench` writes the report at the end of a sweep, but a single program is
often re-run afterwards with `rosetta migrate` - because it hit a transient
network error, or because a fix landed that affects only it. This rebuilds
report.md and results.json from the per-program result.json files so the
aggregate always reflects the artefacts actually on disk.

    python3 scripts/rebuild_report.py out
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rosetta.models import DiffResult, MigrationResult  # noqa: E402
from rosetta.report import to_json, to_markdown  # noqa: E402


def load(out: Path) -> list[MigrationResult]:
    results: list[MigrationResult] = []
    for rj in sorted(out.glob("*/result.json")):
        d = json.loads(rj.read_text())
        migrated = rj.parent / "migrated.py"
        res = MigrationResult(
            program_id=d["program_id"],
            path=d["path"],
            loc=d["loc"],
            equivalent=d["equivalent"],
            vectors_total=d["vectors_total"],
            vectors_passed=d["vectors_passed"],
            repair_iterations=d["repair_iterations"],
            python_code=migrated.read_text() if migrated.exists() else "",
            token_usage=d.get("token_usage", {}),
            error=d.get("error"),
        )
        # Failing vectors are persisted, so the report's note column can name
        # the mismatch kinds rather than just saying "no".
        res.diffs = [
            DiffResult(
                vid=x.get("vid", ""),
                equal=False,
                kind=x.get("kind", ""),
                detail=x.get("detail", ""),
                stdin=x.get("stdin", ""),
            )
            for x in d.get("diffs", [])
        ]
        results.append(res)
    return results


def main(out_dir: str = "out") -> int:
    out = Path(out_dir)
    results = load(out)
    if not results:
        print(f"no */result.json under {out}", file=sys.stderr)
        return 1

    to_json(results, out / "results.json")
    (out / "report.md").write_text(to_markdown(results))

    equiv = sum(1 for r in results if r.equivalent)
    vectors = sum(r.vectors_total for r in results)
    passed = sum(r.vectors_passed for r in results)
    print(f"{equiv}/{len(results)} equivalent, {passed}/{vectors} vectors -> {out/'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
