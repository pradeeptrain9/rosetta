"""Sandboxed differential execution.

Docker is the default backend so the project runs on a machine with no GnuCOBOL
installed (and so untrusted generated Python never executes on the host with
network access). The container runs with no network, a memory cap and a pid cap.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .models import CobolProgram, RunResult, TestVector

DRIVER = Path(__file__).with_name("sandbox_driver.py")


class SandboxError(RuntimeError):
    pass


@dataclass
class BatchOutcome:
    compile_ok: bool
    compile_stderr: str
    runs: dict[str, tuple[RunResult, RunResult]]  # vid -> (reference, migrated)


class Sandbox:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.backend = settings.sandbox
        if self.backend == "local" and not shutil.which("cobc"):
            raise SandboxError(
                "ROSETTA_SANDBOX=local but `cobc` is not on PATH. Install GnuCOBOL "
                "(`brew install gnu-cobol`) or use the docker backend."
            )
        if self.backend == "docker" and not shutil.which("docker"):
            raise SandboxError("docker not found on PATH. Set ROSETTA_SANDBOX=local.")

    # ---------- image ----------

    def build_image(self) -> None:
        if self.backend != "docker":
            return
        root = Path(__file__).resolve().parent.parent
        cmd = ["docker", "build", "-t", self.settings.sandbox_image, "-f", str(root / "Dockerfile"), str(root)]
        proc = subprocess.run(cmd, text=True)
        if proc.returncode != 0:
            raise SandboxError("docker build failed; see output above")

    def image_present(self) -> bool:
        if self.backend != "docker":
            return True
        proc = subprocess.run(
            ["docker", "image", "inspect", self.settings.sandbox_image],
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0

    # ---------- execution ----------

    def run_batch(
        self,
        prog: CobolProgram,
        python_code: str,
        vectors: list[TestVector],
    ) -> BatchOutcome:
        with tempfile.TemporaryDirectory(prefix="rosetta-") as tmp:
            # resolve(): on macOS the temp dir sits under /var/folders, which is
            # a symlink into /private. Docker needs the real path to bind mount it.
            work = Path(tmp).resolve()
            cobol_name = "program.cbl"
            py_name = "migrated.py"
            (work / cobol_name).write_text(prog.source)
            (work / py_name).write_text(python_code)
            (work / "job.json").write_text(
                json.dumps(
                    {
                        "cobol": cobol_name,
                        "python": py_name,
                        "free_format": prog.free_format,
                        "timeout": self.settings.timeout_sec,
                        "vectors": [{"vid": v.vid, "stdin": v.stdin} for v in vectors],
                    }
                )
            )
            shutil.copy(DRIVER, work / "driver.py")

            raw = self._execute_driver(work, len(vectors))
            return _parse_outcome(raw)

    def _execute_driver(self, work: Path, n_vectors: int) -> str:
        # Generous outer budget: per-vector timeout x 2 programs x vectors, plus
        # compile time, so the driver can always finish and report partials.
        budget = self.settings.timeout_sec * 2 * max(n_vectors, 1) + 120

        if self.backend == "local":
            cmd = ["python3", str(work / "driver.py")]
            env_extra = {"ROSETTA_WORKDIR": str(work)}
        else:
            cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", "1g",
                "--pids-limit", "256",
                "-v", f"{work}:/work",
                "-w", "/work",
                "-e", "ROSETTA_WORKDIR=/work",
                "-e", "HOME=/tmp",
            ]
            # The bind mount is owned by the host user, and cobc has to write the
            # compiled reference binary into it. Running as the image's own user
            # would fail on permissions, so the container takes the host uid.
            if hasattr(os, "getuid"):
                cmd += ["--user", f"{os.getuid()}:{os.getgid()}"]
            cmd += [
                self.settings.sandbox_image,
                "python3", "/work/driver.py",
            ]
            env_extra = {}

        env = {**os.environ, **env_extra}
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=budget, env=env, errors="replace"
            )
        except subprocess.TimeoutExpired:
            raise SandboxError(f"sandbox batch exceeded {budget}s")

        if proc.returncode != 0 and not proc.stdout.strip():
            hint = ""
            if self.backend == "docker" and "Unable to find image" in proc.stderr:
                hint = " Run `rosetta sandbox-build` first."
            raise SandboxError(f"sandbox driver failed: {proc.stderr[-2000:]}{hint}")
        return proc.stdout


def _rr(d: dict) -> RunResult:
    return RunResult(
        stdout=d.get("stdout", ""),
        stderr=d.get("stderr", ""),
        exit_code=int(d.get("exit_code", -1)),
        duration_ms=int(d.get("duration_ms", 0)),
        timed_out=bool(d.get("timed_out")),
    )


def _parse_outcome(raw: str) -> BatchOutcome:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SandboxError(f"sandbox returned non-JSON output: {raw[:500]!r}") from exc

    comp = data.get("compile", {})
    runs = {
        r["vid"]: (_rr(r.get("ref", {})), _rr(r.get("py", {})))
        for r in data.get("results", [])
    }
    return BatchOutcome(
        compile_ok=bool(comp.get("ok")),
        compile_stderr=str(comp.get("stderr", "")),
        runs=runs,
    )
