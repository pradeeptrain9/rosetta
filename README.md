# Rosetta

**COBOL → Python migration with machine-checked behavioural equivalence.**

Built with **NVIDIA Nemotron** models served on **Nebius Token Factory**.

---

## The problem

There are an estimated 800 billion lines of COBOL still in production, running
core banking, insurance policy administration, tax systems and payroll. Nobody
is writing new COBOL; almost nobody left can read the old COBOL. Migration is
done by hand, at consultancy day rates, and it takes years.

LLMs can translate COBOL to Python in seconds. That is not the hard part, and
it is not the part anyone will pay for. The hard part is the question a bank's
risk committee asks next:

> How do you know the new code does the same thing as the old code?

"A large language model is confident about it" is not an answer when the
program computes interest on customer deposits. One truncated cent, repeated
across ten million accounts, is a regulatory incident.

## What Rosetta does

Rosetta treats migration as a **verification** problem rather than a
translation problem. It never asks a model whether its output is correct. It
compiles the original COBOL with GnuCOBOL, runs both programs against the same
inputs, and compares stdout byte for byte.

```
COBOL source
    │
    ├─► static analysis            deterministic: PIC clauses, ACCEPT count, format
    │                              (parsed, never asked of a model)
    │
    ├─► I/O contract               Nemotron fast tier
    │
    ├─► test vectors               boundary probes derived from the PIC clauses
    │                              + Nemotron fast tier for branch coverage
    │
    ├─► translation                Nemotron reasoning tier
    │
    ├─► differential execution     GnuCOBOL binary vs migrated Python,
    │                              same stdin, sandboxed, no network
    │
    ├─► mismatch?  ──► repair      Nemotron reasoning tier sees the failing
    │       ▲                      input, both outputs, and the diff
    │       └──────────────────────┘  loop until equivalent or budget spent
    │
    └─► equivalence report         per-program pass/fail with the vector count
```

A program is only marked migrated when **every** vector matches. Everything
else is reported as a failure with the diff attached, because a migration tool
that hides its failures is worse than no tool.

## Why this needs a reasoning model

Naive COBOL translation fails on a small, specific set of semantics, and it
fails silently — the output looks plausible and is wrong in the last decimal
place. The ones that actually break ports:

| COBOL semantic | What a naive port does | Consequence |
|---|---|---|
| `COMPUTE` truncates toward zero unless `ROUNDED` | uses float, or rounds half-even | cents drift, compounding per iteration |
| `ROUNDED` is half **away from zero** | Python's `round()` is half-to-even | every `x.5` case is wrong |
| `PIC 9(5)` silently drops the high-order digit on overflow | Python ints grow | overflow goes undetected |
| `DISPLAY` of `PIC X(12)` emits exactly 12 bytes | strips padding | downstream fixed-width parsers break |
| Edited pictures (`ZZ,ZZ9.99CR`) | approximates the format | report output mismatches |
| `PERFORM VARYING` leaves the control variable past the bound | off by one | wrong value if displayed after the loop |

Each of these is a reasoning task, not a pattern match: the model has to carry
the scale of every field through an expression tree and decide where the
quantisation happens. That is why translation and repair run on the reasoning
tier while the high-volume work does not.

## How the Nemotron tiers are used

Three tiers, routed by job, because the pipeline's cost is dominated by
whichever tier does the repetitive work:

| Tier | Job | Why this tier |
|---|---|---|
| **reason** (Nemotron 3 Ultra) | translation, repair diagnosis | needs to track fixed-point scale through expressions and diagnose a diff's root cause |
| **fast** (Nemotron 3 Nano) | I/O contract extraction, test-vector generation | high call volume, structured output, no deep reasoning required |
| **mid** (Nemotron 3 Super) | distillation comparison baseline | measures what is lost by dropping a tier |
| **student** (Llama 3.1 8B) | distilled repair, fine-tuned | the only tier that is *not* a Nemotron, because Token Factory fine-tunes none of them |

The three Nemotron tiers are **discovered, not hard-coded**. `rosetta models
--resolve` reads `GET /v1/models` from Token Factory and picks each tier by
matching the served ids, caching the result — so the project keeps working as
ids rotate. Pin them explicitly with `ROSETTA_MODEL_REASON`,
`ROSETTA_MODEL_FAST` and `ROSETTA_MODEL_MID` if you prefer.

The student is the exception: it is a fixed id from `ROSETTA_MODEL_STUDENT`,
because being *served* and being *fine-tunable* are different properties and
discovery would happily hand back a model the fine-tuning API then rejects.

## Where Token Factory does the heavy lifting

1. **Serving the three tiers behind one OpenAI-compatible endpoint.** Tier
   routing is a string swap, so measuring "what if the fast tier did this job"
   costs one config change rather than a rewrite.
2. **Serverless AI Jobs for the differential sweep.** Verification, not
   inference, is the expensive stage: every program runs its whole vector suite
   twice per repair iteration. Serverless AI jobs have no replica flag — one job
   is one container run — so `jobs/submit_sweep.sh N` submits N independent jobs,
   each told which slice of the corpus it owns via `ROSETTA_SHARD_INDEX` and
   `ROSETTA_SHARD_COUNT`. `jobs/run_shard.py` stride-partitions on those, which
   keeps shards balanced with no coordinator, and `jobs/merge_shards.py`
   reassembles one report. The replicas are plain CPU workers: the GPU work all
   happens inside Token Factory.
3. **Fine-tuning for distillation.** Every accepted repair is a labelled
   example — failing input, both outputs, and the fix that worked. `rosetta
   distill-export` writes them as chat JSONL and `rosetta distill-train` starts
   a LoRA fine-tune on Token Factory. This is **cross-model** distillation:
   Token Factory fine-tunes no Nemotron model, so Nemotron Ultra generates the
   labels and a smaller fine-tunable student (Llama, Qwen, Gemma or gpt-oss)
   learns them. Repairs that *regressed* are excluded — imitating a bad fix
   makes the student worse.

## Quick start

```bash
git clone <this repo> && cd rosetta
./scripts/setup.sh          # venv, deps, .env, sandbox image
```

Add your Nebius key to `.env`:

```
NEBIUS_API_KEY=your_key_here
```

Then:

```bash
source .venv/bin/activate

./scripts/verify_corpus.sh                # free: compile + run all 20 programs
rosetta models --resolve                  # show the Nemotron tier routing
rosetta analyze benchmarks/programs/interest.cbl   # static analysis, no API calls
rosetta migrate benchmarks/programs/interest.cbl   # one program
rosetta bench benchmarks/programs                  # the whole suite + report
```

Artefacts land in `out/`:

```
out/
  INTEREST/migrated.py      the Python port
  INTEREST/result.json      every failing vector with its diff
  report.md                 the equivalence table
  results.json
```

## Requirements

- Python 3.10+
- Docker (default sandbox — **no local GnuCOBOL needed**)
- A Nebius Token Factory API key — `NEBIUS_API_KEY`, the only credential the
  pipeline needs. The Serverless AI Jobs sweep additionally needs the Nebius AI
  Cloud CLI configured and a registry to push `Dockerfile.job` to, but the sweep
  also runs locally via `rosetta bench --workers N`.

To run without Docker, install GnuCOBOL (`brew install gnu-cobol`,
`apt install gnucobol4`) and set `ROSETTA_SANDBOX=local`.

## Sandboxing

Model-generated Python is untrusted code. It executes in a container with
`--network none`, a 1 GB memory cap, a 256 pid cap, a per-run wall-clock
timeout, and as an unprivileged user. The driver batches all vectors into one
container invocation, so a 40-vector suite takes seconds rather than a minute
of container startup.

## The benchmark programs

`benchmarks/programs/` holds 20 fixed-format COBOL programs. Each one is built
around a specific semantic that silently breaks naive ports, stated in the
file's header comment:

| Program | Trap |
|---|---|
| `interest.cbl` | per-iteration truncation compounds over N years |
| `payroll.cbl` | `ROUNDED` store adjacent to a truncated one, `EVALUATE` fall-through |
| `invoice.cbl` | field overflow drops a digit; edited `CR` sign picture |
| `checkdig.cbl` | `PERFORM VARYING` exit value; non-numeric bytes via reference modification |
| `gradebook.cbl` | fixed-width alphanumeric padding and truncation; inclusive boundaries |
| `roundmode.cbl` | truncate vs round-half-away-from-zero on the same value; `DIVIDE ... REMAINDER` |
| `sizerr.cbl` | `ON SIZE ERROR` leaves the field untouched; without it the high digits vanish |
| `signdisp.cbl` | sign overpunch, `SIGN IS LEADING/TRAILING SEPARATE`, floating `-`/`+` pictures |
| `inspectrep.cbl` | `INSPECT TALLYING` accumulates rather than resets; `LEADING` stops early |
| `stringops.cbl` | `STRING`/`UNSTRING` with `POINTER`; `DELIMITED BY SIZE` keeps padding |
| `refmod.cbl` | `(start:len)` is a length not an end; partially written destinations |
| `tablesum.cbl` | `SEARCH` leaves the index one past the table on `AT END` |
| `condname.cbl` | `AND` binds tighter than `OR`; abbreviated combined relations |
| `evalrange.cbl` | first matching `WHEN` wins; `ANY` makes later branches dead code |
| `datecalc.cbl` | integer date intrinsics; signed `REMAINDER` takes the dividend's sign |
| `currency.cbl` | floating `$` position moves with magnitude; `*` protection; `BLANK WHEN ZERO` |
| `compfield.cbl` | `COMP`/`COMP-3` truncate to the picture; `FUNCTION LENGTH` returns bytes |
| `bubblesort.cbl` | one `ACCEPT` inside a loop consumes eight stdin lines |
| `loanamort.cbl` | truncation accumulates across an input-dependent number of output lines |
| `statemach.cbl` | `WITH TEST AFTER` runs the body once regardless; compound `OR` exit value |

All 20 compile under GnuCOBOL 4.0 and run to a clean exit. Verify before
spending any credits:

```bash
./scripts/verify_corpus.sh
```

That compiles every program and runs it against its fixture in
`benchmarks/smoke/`. It needs no API key. Two failures it catches that would
otherwise waste a whole sweep: a program that will not compile (there is then
no oracle to compare against) and a program whose trap never fires (its
equivalence would be proven trivially).

### A note on scaled input

`ACCEPT` into a `V`-scaled numeric field reads stdin as an **integer**, so
`0500` moved into `PIC 9(2)V99` lands as `00.00`, not `5.00` — the value
overflows the two integer digit positions and the fraction is never populated.
Programs that need a real fraction therefore accept an integer (basis points,
thousandths) and scale it with `COMPUTE`. Three programs in this corpus were
rewritten for exactly that reason: without it their rates were zero and the
truncation they exist to demonstrate never happened.

Point `rosetta bench` at any directory of `.cbl` / `.cob` files to run your own.

## Honest limitations

- **Batch programs with stdin/stdout only.** `CALL`, `EXEC SQL`, `EXEC CICS`,
  `COPY` books, `SORT`, indexed file I/O and `GO TO` are detected by the static
  analyser and reported as flagged constructs rather than silently mistranslated.
- **Equivalence is over the generated vector suite, not a proof over all
  inputs.** It is bounded verification: strong evidence, not a theorem. The
  vector count is printed next to every result so the strength of the claim is
  visible rather than implied.
- **GnuCOBOL is the oracle.** Where GnuCOBOL's `ACCEPT` conversion or sign
  handling differs from IBM Enterprise COBOL, Rosetta reproduces GnuCOBOL. For
  a mainframe migration the oracle should be the mainframe compiler.
- **Non-deterministic programs cannot be verified this way.** Programs reading
  the system date, time or random source are flagged in the contract notes.

## Layout

```
rosetta/
  config.py          settings, Nemotron tier discovery and routing
  llm.py             Token Factory client, token ledger, retry
  cobol.py           deterministic static analysis (PIC expansion, format detection)
  spec.py            I/O contract extraction          [fast tier]
  testgen.py         boundary probes + generated vectors [fast tier]
  translate.py       COBOL -> Python                   [reasoning tier]
  sandbox.py         container-backed differential execution
  sandbox_driver.py  in-sandbox batch runner
  differ.py          output normalisation, mismatch classification
  repair.py          repair loop                       [reasoning tier]
  pipeline.py        per-program orchestration
  report.py          equivalence report + token accounting
  distill.py         trace export, Token Factory fine-tune
  cli.py             command line
jobs/
  run_shard.py       Serverless AI Jobs shard entrypoint
  submit_sweep.sh    submits N shard jobs via the nebius CLI
  merge_shards.py    report assembly
Dockerfile           the sandbox (GnuCOBOL + CPython, no app code)
Dockerfile.job       sandbox + Rosetta source, for job replicas
benchmarks/
  programs/          20-program COBOL corpus, one trap each
  smoke/             one stdin fixture per program
scripts/
  setup.sh           venv, deps, sandbox image
  verify_corpus.sh   compile + run the corpus, no API key needed
```

## License

Apache 2.0. See [LICENSE](LICENSE).
