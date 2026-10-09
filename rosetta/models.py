"""Data types passed between pipeline stages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class CobolField:
    name: str
    level: int
    pic: str | None
    usage: str | None          # COMP, COMP-3, DISPLAY, ...
    digits: int = 0            # total 9s
    scale: int = 0             # digits right of V
    signed: bool = False
    alpha_len: int = 0         # X(n) length, 0 if numeric

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CobolProgram:
    path: str
    program_id: str
    source: str
    free_format: bool
    loc: int
    accept_count: int
    display_count: int
    fields: list[CobolField] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    file_selects: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


@dataclass
class IOContract:
    """What the program reads and writes. Drives test-vector generation."""

    stdin_lines: int
    stdin_fields: list[dict[str, Any]] = field(default_factory=list)
    stdout_description: str = ""
    reads_files: bool = False
    notes: str = ""


@dataclass
class TestVector:
    # Unannotated, so dataclass does not treat it as a field. Stops pytest from
    # trying to collect this as a test class because of the name.
    __test__ = False

    vid: str
    stdin: str
    origin: str                # "boundary" | "llm" | "repair-regression"
    note: str = ""

    @staticmethod
    def make(stdin: str, origin: str, note: str = "") -> "TestVector":
        h = hashlib.sha1(stdin.encode("utf-8", "replace")).hexdigest()[:10]
        return TestVector(vid=f"{origin[:3]}-{h}", stdin=stdin, origin=origin, note=note)


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    timed_out: bool = False


@dataclass
class DiffResult:
    vid: str
    equal: bool
    kind: str                  # EQUAL | STDOUT_DIFF | EXIT_DIFF | PY_CRASH | REF_CRASH | TIMEOUT
    detail: str = ""
    stdin: str = ""


@dataclass
class RepairAttempt:
    iteration: int
    failures_before: int
    failures_after: int
    failure_kinds: list[str]
    diff_excerpt: str
    patched_code: str


@dataclass
class MigrationResult:
    program_id: str
    path: str
    loc: int
    equivalent: bool
    vectors_total: int
    vectors_passed: int
    repair_iterations: int
    python_code: str
    diffs: list[DiffResult] = field(default_factory=list)
    repairs: list[RepairAttempt] = field(default_factory=list)
    token_usage: dict[str, dict[str, int]] = field(default_factory=dict)
    error: str | None = None

    @property
    def pass_rate(self) -> float:
        return self.vectors_passed / self.vectors_total if self.vectors_total else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "path": self.path,
            "loc": self.loc,
            "equivalent": self.equivalent,
            "vectors_total": self.vectors_total,
            "vectors_passed": self.vectors_passed,
            "pass_rate": round(self.pass_rate, 4),
            "repair_iterations": self.repair_iterations,
            "token_usage": self.token_usage,
            "error": self.error,
        }
