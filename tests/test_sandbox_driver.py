"""Driver mechanics, verified without GnuCOBOL.

A stub `cobc` on PATH stands in for the real compiler: it emits an executable
`ref` that behaves like a compiled COBOL program. That exercises the parts of
the driver that can break independently of COBOL itself - the compile step, the
per-vector batch loop, stdin delivery, timeout handling and the JSON contract
that sandbox.py parses.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rosetta.sandbox import _parse_outcome

DRIVER = Path(__file__).resolve().parent.parent / "rosetta" / "sandbox_driver.py"

# Stub compiler: ignores the COBOL entirely and writes a `ref` program that
# doubles the first stdin line, zero-padded to five digits like PIC 9(5).
FAKE_COBC = """#!/bin/sh
out=ref
while [ $# -gt 0 ]; do
  case "$1" in
    -o) shift; out="$1" ;;
  esac
  shift
done
cat > "$out" <<'INNER'
#!/bin/sh
read line
printf 'VALUE %05d\\n' "$((line * 2))" 2>/dev/null || printf 'VALUE 00000\\n'
INNER
chmod +x "$out"
"""

FAKE_COBC_FAILING = """#!/bin/sh
echo "program.cbl:12: error: syntax error, unexpected GARBAGE" >&2
exit 1
"""


def _write_stub(tmp_path: Path, body: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    cobc = bindir / "cobc"
    cobc.write_text(body)
    cobc.chmod(0o755)
    return bindir


def _run_driver(work: Path, bindir: Path) -> dict:
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
           "ROSETTA_WORKDIR": str(work)}
    proc = subprocess.run(
        [sys.executable, str(DRIVER)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _job(work: Path, python_body: str, vectors: list[dict], timeout: float = 10) -> None:
    (work / "program.cbl").write_text("       PROGRAM-ID. STUB.\n")
    (work / "migrated.py").write_text(python_body)
    (work / "job.json").write_text(json.dumps({
        "cobol": "program.cbl",
        "python": "migrated.py",
        "free_format": False,
        "timeout": timeout,
        "vectors": vectors,
    }))


MATCHING_PY = """import sys
line = sys.stdin.readline().strip()
print("VALUE %05d" % (int(line) * 2))
"""

WRONG_PY = """import sys
line = sys.stdin.readline().strip()
print("VALUE %d" % (int(line) * 2))   # missing the zero padding
"""

HANGING_PY = """import time
time.sleep(30)
"""


def test_driver_reports_equal_runs(tmp_path):
    bindir = _write_stub(tmp_path, FAKE_COBC)
    work = tmp_path / "work"
    work.mkdir()
    _job(work, MATCHING_PY, [{"vid": "v1", "stdin": "21\n"}, {"vid": "v2", "stdin": "5\n"}])

    data = _run_driver(work, bindir)
    assert data["compile"]["ok"], data["compile"]
    assert len(data["results"]) == 2

    outcome = _parse_outcome(json.dumps(data))
    assert outcome.compile_ok
    ref, got = outcome.runs["v1"]
    assert ref.stdout.strip() == "VALUE 00042"
    assert got.stdout.strip() == "VALUE 00042"


def test_driver_surfaces_a_formatting_mismatch(tmp_path):
    bindir = _write_stub(tmp_path, FAKE_COBC)
    work = tmp_path / "work"
    work.mkdir()
    _job(work, WRONG_PY, [{"vid": "v1", "stdin": "21\n"}])

    outcome = _parse_outcome(json.dumps(_run_driver(work, bindir)))
    ref, got = outcome.runs["v1"]
    assert ref.stdout.strip() == "VALUE 00042"
    assert got.stdout.strip() == "VALUE 42"

    from rosetta.differ import compare
    from rosetta.models import TestVector

    diff = compare(TestVector.make("21\n", "boundary"), ref, got)
    assert not diff.equal and diff.kind == "STDOUT_DIFF"


def test_driver_times_out_the_migrated_program_without_killing_the_batch(tmp_path):
    bindir = _write_stub(tmp_path, FAKE_COBC)
    work = tmp_path / "work"
    work.mkdir()
    _job(work, HANGING_PY, [{"vid": "v1", "stdin": "1\n"}], timeout=2)

    outcome = _parse_outcome(json.dumps(_run_driver(work, bindir)))
    _, got = outcome.runs["v1"]
    assert got.timed_out


def test_driver_reports_compile_failure_and_runs_nothing(tmp_path):
    bindir = _write_stub(tmp_path, FAKE_COBC_FAILING)
    work = tmp_path / "work"
    work.mkdir()
    _job(work, MATCHING_PY, [{"vid": "v1", "stdin": "1\n"}])

    data = _run_driver(work, bindir)
    assert not data["compile"]["ok"]
    assert "syntax error" in data["compile"]["stderr"]
    # A reference that will not compile means there is no oracle, so the driver
    # must not report any vector as passing.
    assert data["results"] == []


def test_parse_outcome_rejects_non_json():
    from rosetta.sandbox import SandboxError

    with pytest.raises(SandboxError):
        _parse_outcome("docker: command not found")
