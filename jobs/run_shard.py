"""Shard entrypoint for Nebius Serverless Jobs.

The differential harness is the expensive part of the pipeline: every program
runs its full vector suite against two binaries, and every repair iteration
runs it again. That work is embarrassingly parallel across programs, so a
benchmark sweep is dispatched as N job replicas, each taking a disjoint slice
of the program list and writing its own results file.

Each replica is given its index via the environment, which is how Nebius
Serverless Jobs exposes replica identity:

    ROSETTA_SHARD_INDEX  (0-based)
    ROSETTA_SHARD_COUNT
    ROSETTA_PROGRAMS_DIR
    ROSETTA_OUTPUT_DIR
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rosetta.config import Settings, load_dotenv, resolve_models  # noqa: E402
from rosetta.llm import LLMClient  # noqa: E402
from rosetta.pipeline import migrate_program  # noqa: E402
from rosetta.report import to_json  # noqa: E402
from rosetta.sandbox import Sandbox  # noqa: E402


def main() -> int:
    load_dotenv()
    index = int(os.environ.get("ROSETTA_SHARD_INDEX", "0"))
    count = max(int(os.environ.get("ROSETTA_SHARD_COUNT", "1")), 1)
    programs_dir = Path(os.environ.get("ROSETTA_PROGRAMS_DIR", "benchmarks/programs"))
    output_dir = Path(os.environ.get("ROSETTA_OUTPUT_DIR", "out"))

    if index >= count:
        print(f"shard index {index} >= count {count}", file=sys.stderr)
        return 2

    settings = Settings.from_env()
    client = LLMClient(settings)
    routing = resolve_models(served=client.served_models())
    sandbox = Sandbox(settings)

    sources = sorted(
        p for p in programs_dir.rglob("*") if p.suffix.lower() in {".cbl", ".cob", ".cobol"}
    )
    mine = sources[index::count]  # stride partition keeps shard sizes balanced
    print(f"shard {index}/{count}: {len(mine)} of {len(sources)} programs", flush=True)

    results = []
    for src in mine:
        results.append(
            migrate_program(
                src,
                LLMClient(settings),
                routing,
                settings,
                sandbox,
                log=lambda m: print(m, flush=True),
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    shard_out = output_dir / f"shard-{index:03d}.json"
    to_json(results, shard_out)
    for r in results:
        d = output_dir / r.program_id
        d.mkdir(parents=True, exist_ok=True)
        if r.python_code:
            (d / "migrated.py").write_text(r.python_code)
        (d / "result.json").write_text(json.dumps(r.summary(), indent=2))

    equiv = sum(1 for r in results if r.equivalent)
    print(f"shard {index}: {equiv}/{len(results)} proven equivalent -> {shard_out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
