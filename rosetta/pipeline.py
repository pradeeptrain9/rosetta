"""End-to-end migration of a single COBOL program."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import cobol, spec, testgen, translate as translate_mod
from .config import ModelRouting, Settings
from .differ import compare, representative_failures
from .llm import LLMClient, TokenLedger
from .models import MigrationResult, TestVector
from .repair import repair
from .sandbox import Sandbox, SandboxError

Logger = Callable[[str], None]


def _noop(msg: str) -> None:
    pass


def migrate_program(
    path: str | Path,
    client: LLMClient,
    routing: ModelRouting,
    settings: Settings,
    sandbox: Sandbox,
    log: Logger = _noop,
) -> MigrationResult:
    ledger = TokenLedger()
    client.ledger = ledger  # per-program accounting

    prog = cobol.analyze(path)
    log(f"[{prog.program_id}] {prog.loc} lines, {prog.accept_count} ACCEPT, format={'free' if prog.free_format else 'fixed'}")
    if prog.unsupported:
        log(f"[{prog.program_id}] flagged constructs: {', '.join(prog.unsupported)}")

    result = MigrationResult(
        program_id=prog.program_id,
        path=str(path),
        loc=prog.loc,
        equivalent=False,
        vectors_total=0,
        vectors_passed=0,
        repair_iterations=0,
        python_code="",
    )

    try:
        try:
            contract = spec.extract_contract(client, routing.fast, prog)
        except (ValueError, RuntimeError) as exc:
            # Degrade rather than abandon the program: the PIC clauses already
            # carry enough to probe it, and vector generation still reads the
            # real source.
            log(f"[{prog.program_id}] [warn] contract unavailable ({exc}); "
                f"falling back to static analysis")
            contract = spec.fallback_contract(prog)
        log(f"[{prog.program_id}] contract: {contract.stdin_lines} stdin line(s), {len(contract.stdin_fields)} field(s)")

        vectors: list[TestVector] = testgen.build_suite(
            client,
            routing.fast,
            prog.source,
            contract,
            target=settings.test_vectors,
            log=log,
        )
        log(f"[{prog.program_id}] {len(vectors)} test vectors "
            f"({sum(1 for v in vectors if v.origin == 'boundary')} boundary, "
            f"{sum(1 for v in vectors if v.origin == 'llm')} generated)")

        code = translate_mod.translate(
            client, routing.reason, prog, contract, fallback_model=routing.mid
        )
        log(f"[{prog.program_id}] translated ({len(code.splitlines())} lines of Python)")

        diffs = _evaluate(sandbox, prog, code, vectors)
        passed = sum(1 for d in diffs if d.equal)
        log(f"[{prog.program_id}] initial equivalence {passed}/{len(vectors)}")

        iteration = 0
        while passed < len(vectors) and iteration < settings.max_repair_iters:
            iteration += 1
            failures = representative_failures(diffs)
            if not failures:
                break
            kinds = ", ".join(sorted({f.kind for f in failures}))
            log(f"[{prog.program_id}] repair {iteration}: {len(vectors) - passed} failing ({kinds})")

            candidate, attempt = repair(
                client,
                routing.reason,
                prog,
                code,
                failures,
                len(vectors),
                iteration,
                n_failing=len(vectors) - passed,
                fallback_model=routing.mid,
            )
            cand_diffs = _evaluate(sandbox, prog, candidate, vectors)
            cand_passed = sum(1 for d in cand_diffs if d.equal)
            attempt.failures_after = len(vectors) - cand_passed
            result.repairs.append(attempt)

            if cand_passed > passed:
                code, diffs, passed = candidate, cand_diffs, cand_passed
                log(f"[{prog.program_id}] repair {iteration} accepted -> {passed}/{len(vectors)}")
            else:
                # A regression is kept out of the result but still recorded, so
                # the distillation set learns which repairs do not work.
                log(f"[{prog.program_id}] repair {iteration} rejected "
                    f"({cand_passed}/{len(vectors)}, no improvement)")

        result.python_code = code
        result.diffs = diffs
        result.vectors_total = len(vectors)
        result.vectors_passed = passed
        result.repair_iterations = iteration
        result.equivalent = passed == len(vectors) and len(vectors) > 0

    except SandboxError as exc:
        result.error = f"sandbox: {exc}"
        log(f"[{prog.program_id}] SANDBOX ERROR: {exc}")
    except (RuntimeError, ValueError) as exc:
        result.error = str(exc)
        log(f"[{prog.program_id}] ERROR: {exc}")

    result.token_usage = ledger.as_dict()
    return result


def _evaluate(sandbox: Sandbox, prog, code: str, vectors: list[TestVector]):
    outcome = sandbox.run_batch(prog, code, vectors)
    if not outcome.compile_ok:
        raise SandboxError(
            f"GnuCOBOL could not compile the reference program: {outcome.compile_stderr[:800]}"
        )
    diffs = []
    for vec in vectors:
        pair = outcome.runs.get(vec.vid)
        if pair is None:
            continue
        ref, got = pair
        diffs.append(compare(vec, ref, got))
    return diffs
