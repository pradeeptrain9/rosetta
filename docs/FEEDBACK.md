# Feedback on Nebius Token Factory and NVIDIA tooling

Fill this in from the actual build before submitting — concrete notes score
better than praise, and the organisers explicitly ask for them.

## Nebius Token Factory

**Worked well**
- OpenAI-compatible surface meant the official `openai` SDK worked unchanged;
  tier routing became a string swap rather than a client rewrite.
- `GET /v1/models` made model discovery possible, so the project pins nothing
  and keeps working as ids rotate.

**Friction** (record as encountered)
- Model id discoverability: _<did the Nemotron tier naming make Ultra / Super /
  Nano unambiguous from the id alone?>_
- Rate limits hit during test-vector generation at _<N>_ concurrent calls;
  observed behaviour: _<status code, retry-after header present or not>_
- Fine-tuning: _<which base models accepted a LoRA job, how long it queued,
  whether the resulting adapter was immediately servable>_
- Reasoning-tier output: _<did `<think>` blocks appear, and was there a
  parameter to suppress them rather than stripping client-side?>_

## NVIDIA Nemotron

**Worked well**
- The reasoning tier handled fixed-point scale propagation through COBOL
  expression trees, which is the actual difficulty in this domain.

**Observations**
- First-pass translation accuracy on the benchmark suite: _<N/5>_
- Most common failure mode before repair: _<e.g. ROUND_HALF_EVEN instead of
  ROUND_HALF_UP, edited-picture formatting>_
- Repair convergence: _<how many iterations typically, and which failure kinds
  never converged>_
- Fast tier on structured JSON output: _<malformed-JSON rate>_

## Nebius Serverless Jobs

- Replica identity: the shard entrypoint assumes an ordinal in the environment.
  _<Confirm the exact variable name the platform injects and note it here —
  this is the one detail a reader will need to reproduce the sweep.>_
- Observed wall-clock for the sweep at _<N>_ replicas vs 1: _<numbers>_
