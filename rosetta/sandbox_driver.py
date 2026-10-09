"""Batch differential runner. Executes inside the sandbox, never on the host.

Reads job.json from the working directory, compiles the COBOL reference once,
then runs the reference binary and the migrated Python against every vector.
Writes a single JSON document to stdout.

Keeping this a batch driver rather than one container per vector is what makes
a 40-vector suite take seconds instead of a minute.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

WORKDIR = os.environ.get("ROSETTA_WORKDIR", os.getcwd())


def _run(cmd: list[str], stdin: str, timeout: float) -> dict:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=WORKDIR,
            errors="replace",
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr[-4000:],
            "exit_code": proc.returncode,
            "duration_ms": int((time.monotonic() - start) * 1000),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"timeout after {timeout}s",
            "exit_code": -1,
            "duration_ms": int((time.monotonic() - start) * 1000),
            "timed_out": True,
        }
    except OSError as exc:
        return {
            "stdout": "",
            "stderr": f"exec failed: {exc}",
            "exit_code": -2,
            "duration_ms": 0,
            "timed_out": False,
        }


def main() -> int:
    with open(os.path.join(WORKDIR, "job.json")) as fh:
        job = json.load(fh)

    timeout = float(job.get("timeout", 10))
    cobol_src = job["cobol"]
    py_src = job["python"]

    compile_cmd = ["cobc", "-x", "-o", "ref", cobol_src]
    if job.get("free_format"):
        compile_cmd.insert(2, "-free")

    comp = subprocess.run(
        compile_cmd, capture_output=True, text=True, cwd=WORKDIR, errors="replace"
    )
    out = {
        "compile": {
            "ok": comp.returncode == 0,
            "stderr": (comp.stderr or comp.stdout)[-4000:],
            "cmd": " ".join(compile_cmd),
        },
        "results": [],
    }
    if comp.returncode != 0:
        json.dump(out, sys.stdout)
        return 0

    ref_bin = os.path.join(WORKDIR, "ref")
    for vec in job.get("vectors", []):
        stdin = vec.get("stdin", "")
        out["results"].append(
            {
                "vid": vec["vid"],
                "ref": _run([ref_bin], stdin, timeout),
                "py": _run([sys.executable, py_src], stdin, timeout),
            }
        )

    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
