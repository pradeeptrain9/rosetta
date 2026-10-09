"""Bake sweep results into the Space image.

The Space must render with no API call: a judge opening it should not depend on
a key being unthrottled at that moment. This reads a completed `rosetta bench`
run out of out/ and writes one self-contained JSON per program, plus an index.

Usage, after a sweep:
    python3 demo/precompute.py out demo/precomputed
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def main(src: str = "out", dst: str = "demo/precomputed") -> int:
    out, target = Path(src), Path(dst)
    if not out.exists():
        print(f"{out} not found - run `rosetta bench benchmarks/programs` first", file=sys.stderr)
        return 1

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    index = []
    for result_file in sorted(out.glob("*/result.json")):
        data = json.loads(result_file.read_text())
        pid = data["program_id"]
        migrated = result_file.parent / "migrated.py"
        cobol_path = Path(data["path"])

        record = {
            **data,
            "python": migrated.read_text() if migrated.exists() else "",
            "cobol": cobol_path.read_text(errors="replace") if cobol_path.exists() else "",
        }
        (target / f"{pid}.json").write_text(json.dumps(record, indent=2))
        index.append(
            {
                "program_id": pid,
                "equivalent": data["equivalent"],
                "vectors_total": data["vectors_total"],
                "vectors_passed": data["vectors_passed"],
                "repair_iterations": data["repair_iterations"],
                "loc": data["loc"],
            }
        )

    index.sort(key=lambda r: (not r["equivalent"], r["program_id"]))
    (target / "index.json").write_text(json.dumps(index, indent=2))

    report = out / "report.md"
    if report.exists():
        shutil.copy(report, target / "report.md")

    equiv = sum(1 for r in index if r["equivalent"])
    print(f"baked {len(index)} programs ({equiv} equivalent) into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
