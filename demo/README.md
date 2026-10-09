---
title: Rosetta COBOL Migration
emoji: 🧮
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Rosetta

COBOL → Python migration with **machine-checked behavioural equivalence**, built
with NVIDIA Nemotron on Nebius Token Factory.

Pick a COBOL program. The page shows the original, the migrated Python, and the
equivalence table: every test input, what the GnuCOBOL-compiled original printed,
and what the port printed. A program counts as migrated only when all of them
match byte for byte.

Source: https://github.com/pradeeptrain9/rosetta

## How this Space works

Results for all 20 corpus programs are **pre-computed and baked into the image**,
so the page renders instantly and still works if the API key is rate-limited.

If `NEBIUS_API_KEY` is set as a Space secret, the *Run live* button re-runs the
full pipeline for one program — contract extraction and test generation on
Nemotron Nano, translation and repair on Nemotron Ultra, then differential
execution against GnuCOBOL inside this container.

## Why you can only pick from a fixed corpus

Model-generated Python is executed to compare it against the original, and in a
Space that execution shares a container with the web server. Running
attacker-chosen input there would be careless, so the demo is restricted to the
20 programs in the repository. The real tool accepts any `.cbl` file and isolates
each run in a container with no network — see the repo for that.
