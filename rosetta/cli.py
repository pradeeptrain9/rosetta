"""Rosetta command line."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import distill as distill_mod
from . import report as report_mod
from .config import Settings, load_dotenv, resolve_models
from .llm import LLMClient
from .models import MigrationResult, RepairAttempt
from .pipeline import migrate_program
from .sandbox import Sandbox, SandboxError

app = typer.Typer(add_completion=False, help="COBOL -> Python migration with proven equivalence.")
console = Console()


def _setup() -> tuple[Settings, LLMClient]:
    load_dotenv()
    settings = Settings.from_env()
    return settings, LLMClient(settings)


@app.command()
def models(resolve: bool = typer.Option(False, "--resolve", help="Re-discover served ids from the endpoint.")) -> None:
    """Show which Nemotron model backs each pipeline tier."""
    settings, client = _setup()
    served = client.served_models()
    routing = resolve_models(served=served, refresh=resolve)

    table = Table(title=f"Nemotron routing via {settings.base_url}")
    table.add_column("Tier")
    table.add_column("Used for")
    table.add_column("Model id")
    table.add_row("reason", "translation + repair", routing.reason)
    table.add_row("fast", "I/O contract + test vectors", routing.fast)
    table.add_row("mid", "distillation comparison", routing.mid)
    console.print(table)

    nemotron = [m for m in served if "nemotron" in m.lower()]
    console.print(f"\n[dim]{len(served)} models served, {len(nemotron)} Nemotron:[/dim]")
    for m in nemotron:
        console.print(f"  [dim]{m}[/dim]")


@app.command("sandbox-build")
def sandbox_build() -> None:
    """Build the GnuCOBOL + Python sandbox image."""
    load_dotenv()
    settings = Settings.from_env()
    sandbox = Sandbox(settings)
    if settings.sandbox == "local":
        console.print("[yellow]ROSETTA_SANDBOX=local; nothing to build.[/yellow]")
        return
    console.print(f"Building [bold]{settings.sandbox_image}[/bold] ...")
    sandbox.build_image()
    console.print("[green]sandbox image ready[/green]")


@app.command()
def migrate(
    path: Path = typer.Argument(..., help="Path to a .cbl / .cob source file."),
    out: Path = typer.Option(Path("out"), "--out", "-o", help="Artefact directory."),
) -> None:
    """Migrate one COBOL program and prove equivalence."""
    settings, client = _setup()
    routing = resolve_models(served=client.served_models())
    sandbox = _ready_sandbox(settings)

    result = migrate_program(path, client, routing, settings, sandbox, log=console.print)
    _persist(result, out)
    _print_one(result)
    raise typer.Exit(0 if result.equivalent else 1)


@app.command()
def bench(
    directory: Path = typer.Argument(Path("benchmarks/programs"), help="Directory of COBOL sources."),
    out: Path = typer.Option(Path("out"), "--out", "-o"),
    limit: int = typer.Option(0, "--limit", help="Only migrate the first N programs."),
    workers: int = typer.Option(4, "--workers", "-w", help="Programs migrated concurrently."),
) -> None:
    """Migrate a directory of programs and write the equivalence report."""
    settings, client = _setup()
    routing = resolve_models(served=client.served_models())
    sandbox = _ready_sandbox(settings)

    sources = sorted(
        p for p in directory.rglob("*") if p.suffix.lower() in {".cbl", ".cob", ".cobol"}
    )
    if limit:
        sources = sources[:limit]
    if not sources:
        console.print(f"[red]No COBOL sources under {directory}[/red]")
        raise typer.Exit(1)

    console.print(f"Migrating [bold]{len(sources)}[/bold] programs with {workers} worker(s)\n")
    results: list[MigrationResult] = []

    # One LLMClient per worker: the ledger is swapped per program, so sharing a
    # client across threads would cross-attribute token usage.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                migrate_program,
                src,
                LLMClient(settings),
                routing,
                settings,
                sandbox,
                console.print,
            ): src
            for src in sources
        }
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # a crashed worker must not lose the run
                console.print(f"[red]{src.name} failed: {exc}[/red]")
                continue
            results.append(res)
            _persist(res, out)

    out.mkdir(parents=True, exist_ok=True)
    report_mod.to_json(results, out / "results.json")
    md = report_mod.to_markdown(results)
    (out / "report.md").write_text(md)

    console.print()
    _print_table(results)
    console.print(f"\nReport written to [bold]{out / 'report.md'}[/bold]")


@app.command("distill-export")
def distill_export(
    out: Path = typer.Option(Path("out"), "--out", "-o"),
    dataset: Path = typer.Option(Path("out/repair-traces.jsonl"), "--dataset"),
) -> None:
    """Export accepted repairs as fine-tuning JSONL."""
    results = _load_results(out)
    n = distill_mod.export_traces(results, dataset)
    console.print(f"Wrote [bold]{n}[/bold] accepted repair traces to {dataset}")
    if n < 10:
        console.print(
            "[yellow]Fewer than 10 examples. Run `rosetta bench` over more programs "
            "before fine-tuning.[/yellow]"
        )


@app.command("distill-train")
def distill_train(
    dataset: Path = typer.Option(Path("out/repair-traces.jsonl"), "--dataset"),
    epochs: int = typer.Option(3, "--epochs"),
) -> None:
    """Upload the trace set and start a Token Factory fine-tune of the fast tier."""
    settings, client = _setup()
    routing = resolve_models(served=client.served_models())
    file_id = distill_mod.upload_dataset(settings, dataset)
    console.print(f"Uploaded dataset: {file_id}")
    job_id = distill_mod.start_finetune(settings, file_id, routing.fast, epochs=epochs)
    console.print(f"Fine-tune job: [bold]{job_id}[/bold] (base {routing.fast})")
    console.print(f"Poll with: [dim]rosetta distill-status {job_id}[/dim]")


@app.command("distill-status")
def distill_status(job_id: str) -> None:
    """Check a fine-tune job."""
    settings, _ = _setup()
    console.print_json(json.dumps(distill_mod.finetune_status(settings, job_id)))


@app.command()
def analyze(path: Path) -> None:
    """Print the static analysis for a COBOL file. No API calls, no cost."""
    from . import cobol

    console.print(cobol.brief(cobol.analyze(path)))


# ---------- helpers ----------


def _ready_sandbox(settings: Settings) -> Sandbox:
    try:
        sandbox = Sandbox(settings)
    except SandboxError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)
    if not sandbox.image_present():
        console.print("[yellow]Sandbox image missing; building it now.[/yellow]")
        sandbox.build_image()
    return sandbox


def _persist(result: MigrationResult, out: Path) -> None:
    d = out / result.program_id
    d.mkdir(parents=True, exist_ok=True)
    if result.python_code:
        (d / "migrated.py").write_text(result.python_code)
    (d / "result.json").write_text(
        json.dumps(
            {
                **result.summary(),
                "diffs": [
                    {"vid": x.vid, "kind": x.kind, "stdin": x.stdin, "detail": x.detail}
                    for x in result.diffs
                    if not x.equal
                ],
                # The patched body and the diff that prompted it are persisted
                # in full: without them `distill-export` run as a separate
                # process has no training examples to export.
                "repairs": [
                    {
                        "iteration": a.iteration,
                        "failures_before": a.failures_before,
                        "failures_after": a.failures_after,
                        "failure_kinds": a.failure_kinds,
                        "diff_excerpt": a.diff_excerpt,
                        "patched_code": a.patched_code,
                    }
                    for a in result.repairs
                ],
            },
            indent=2,
        )
    )


def _load_results(out: Path) -> list[MigrationResult]:
    """Rehydrate enough of each result to export traces."""
    results: list[MigrationResult] = []
    for rj in sorted(out.glob("*/result.json")):
        data = json.loads(rj.read_text())
        res = MigrationResult(
            program_id=data["program_id"],
            path=data["path"],
            loc=data["loc"],
            equivalent=data["equivalent"],
            vectors_total=data["vectors_total"],
            vectors_passed=data["vectors_passed"],
            repair_iterations=data["repair_iterations"],
            python_code=(rj.parent / "migrated.py").read_text()
            if (rj.parent / "migrated.py").exists()
            else "",
            token_usage=data.get("token_usage", {}),
        )
        res.repairs = [
            RepairAttempt(
                iteration=r["iteration"],
                failures_before=r["failures_before"],
                failures_after=r["failures_after"],
                failure_kinds=r.get("failure_kinds", []),
                diff_excerpt=r.get("diff_excerpt", ""),
                patched_code=r.get("patched_code", ""),
            )
            for r in data.get("repairs", [])
        ]
        results.append(res)
    if not results:
        console.print(f"[red]No results under {out}. Run `rosetta bench` first.[/red]")
        raise typer.Exit(1)
    return results


def _print_one(result: MigrationResult) -> None:
    status = "[green]EQUIVALENT[/green]" if result.equivalent else "[red]NOT EQUIVALENT[/red]"
    console.print(
        f"\n{status}  {result.program_id}: {result.vectors_passed}/{result.vectors_total} "
        f"vectors, {result.repair_iterations} repair iteration(s)"
    )
    if result.error:
        console.print(f"[red]{result.error}[/red]")


def _print_table(results: list[MigrationResult]) -> None:
    table = Table(title="Equivalence")
    table.add_column("Program")
    table.add_column("LOC", justify="right")
    table.add_column("Vectors", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Repairs", justify="right")
    table.add_column("Equivalent")
    for r in sorted(results, key=lambda x: (not x.equivalent, x.program_id)):
        table.add_row(
            r.program_id,
            str(r.loc),
            str(r.vectors_total),
            str(r.vectors_passed),
            str(r.repair_iterations),
            "[green]yes[/green]" if r.equivalent else "[red]no[/red]",
        )
    console.print(table)
    equiv = sum(1 for r in results if r.equivalent)
    console.print(f"\n[bold]{equiv}/{len(results)}[/bold] programs proven equivalent")


if __name__ == "__main__":
    app()
