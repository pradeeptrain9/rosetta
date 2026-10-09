# Demo video script (3:00 hard cap)

The judging rubric rewards a working system with numbers on screen. Lead with
the proof, not the architecture.

## 0:00–0:20 — the stake

On screen: a terminal, nothing else.

> "There are roughly 800 billion lines of COBOL still running banks, insurers
> and tax systems. An LLM can translate it in seconds. That's not worth
> anything, because the next question is the only one that matters: how do you
> know the new code does the same thing? Rosetta answers that question with a
> test harness, not a vibe."

## 0:20–0:50 — the trap, shown not told

```bash
cat benchmarks/programs/interest.cbl
```

Point at one line:

```cobol
COMPUTE WS-INTEREST = WS-BALANCE * WS-RATE / 100
```

> "No ROUNDED. COBOL truncates this toward zero to two decimals, every single
> year. A port that keeps full precision is wrong by cents after thirty years,
> and it looks right the whole time."

## 0:50–1:30 — the run

```bash
rosetta models --resolve
rosetta migrate benchmarks/programs/interest.cbl
```

Narrate the live log lines as they stream:

> "Static analysis is parsed, not asked of a model — PIC clauses and the ACCEPT
> count are facts. Nemotron Nano extracts the I/O contract and generates test
> vectors; boundary probes come straight out of the PIC clauses. Nemotron Ultra
> does the translation. Then the harness compiles the original with GnuCOBOL and
> runs both programs against every vector in a sandbox with no network."

When a repair iteration fires, stop and let the viewer read it:

> "There it is. Vector failed, cents off. Ultra gets the failing input, both
> outputs, and the diff. It fixes the quantisation — and now it's 40 out of 40."

## 1:30–2:15 — scale

```bash
rosetta bench benchmarks/programs
cat out/report.md
```

Hold on the equivalence table and the token-usage table.

> "Twenty programs, each one built around a COBOL semantic that breaks naive
> ports. The table shows how many were proven equivalent byte for byte across
> their full vector suite, and the token table shows where the money went:
> Ultra on translation and repair, Nano on everything high-volume."

Then show `jobs/nebius_job.yaml`:

> "Verification is the expensive stage — every program runs its whole suite
> twice per repair iteration. That fans out across Nebius Serverless Jobs,
> stride-partitioned, one replica per shard."

## 2:15–2:45 — the distillation result

```bash
rosetta distill-export
```

> "Every accepted repair is a labelled example: the failing input, both
> outputs, and the fix that worked. Fine-tune Nano on those in Token Factory
> and the repair loop runs on the cheap tier. Repairs that regressed are
> excluded — imitating a bad fix makes the model worse."

Put the before/after cost and pass-rate numbers on screen as text.

## 2:45–3:00 — close on the limitation

> "This is bounded verification, not a theorem — equivalence over the generated
> suite, and the vector count is printed next to every result so you can see
> exactly how strong the claim is. That's still the difference between a
> migration a bank can sign off and a translation nobody can."

---

## Recording checklist

- [ ] Terminal at ≥16pt. Judges watch on laptops.
- [ ] Pre-build the sandbox image. Do not film an `apt-get`.
- [ ] Run `./scripts/verify_corpus.sh` before recording. If a program stopped
      compiling, every equivalence number in the report is meaningless.
- [ ] Do a dry run and keep the `out/` from a **successful** bench as backup
      footage, in case the live run hits an API hiccup.
- [ ] Record one take where a repair iteration actually fires. That moment is
      the whole pitch; if every program passes first try, add a harder program.
- [ ] Say "Nebius Token Factory" and "Nemotron" out loud. The rubric asks how
      they were used.
- [ ] Upload public, not unlisted-only. Under 3:00.

## Submission checklist

- [ ] Track: **Coding and Agentic Engineering**
- [ ] Public repo with Apache 2.0 visible at the top of the page
- [ ] README with setup instructions (done) and explicit Nemotron / Token
      Factory sections (done)
- [ ] Working demo URL — for a CLI tool, the hosted option is a Nebius
      Serverless Endpoint wrapping `migrate` plus a one-page uploader, or a
      Colab/Codespaces link that runs `rosetta bench`
- [ ] 3-minute public YouTube video
- [ ] Feedback on Token Factory / NVIDIA tooling (see `docs/FEEDBACK.md`)
- [ ] If an IRL Builders & Brews city was attended, select it
