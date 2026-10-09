# Rosetta equivalence report

## Headline

- Programs migrated with proven equivalence: **16/20** (80%)
- Equivalent on first translation: **9**
- Equivalent only after repair: **7**
- Differential test vectors executed: **778**, passed **757** (97.30%)

## Per program

| Program | COBOL LOC | Vectors | Passed | Repairs | Equivalent | Note |
|---|---:|---:|---:|---:|:--:|---|
| `BUBBLESORT` | 58 | 39 | 39 | 1 | yes |  |
| `CHECKDIG` | 51 | 39 | 39 | 1 | yes |  |
| `COMPFIELD` | 42 | 33 | 33 | 2 | yes |  |
| `CONDNAME` | 49 | 40 | 40 | 1 | yes |  |
| `DATECALC` | 71 | 40 | 40 | 1 | yes |  |
| `EVALRANGE` | 44 | 40 | 40 | 0 | yes |  |
| `GRADEBOOK` | 51 | 40 | 40 | 1 | yes |  |
| `INSPECTREP` | 32 | 39 | 39 | 0 | yes |  |
| `INVOICE` | 36 | 40 | 40 | 0 | yes |  |
| `LOANAMORT` | 65 | 40 | 40 | 0 | yes |  |
| `REFMOD` | 46 | 40 | 40 | 0 | yes |  |
| `SIGNDISP` | 35 | 40 | 40 | 3 | yes |  |
| `SIZERR` | 31 | 38 | 38 | 0 | yes |  |
| `STATEMACH` | 60 | 39 | 39 | 0 | yes |  |
| `STRINGOPS` | 45 | 39 | 39 | 0 | yes |  |
| `TABLESUM` | 54 | 36 | 36 | 0 | yes |  |
| `CURRENCY` | 34 | 40 | 24 | 3 | no | STDOUT_DIFF |
| `INTEREST` | 38 | 40 | 39 | 3 | no | STDOUT_DIFF |
| `PAYROLL` | 51 | 40 | 38 | 3 | no | STDOUT_DIFF |
| `ROUNDMODE` | 39 | 36 | 34 | 3 | no | STDOUT_DIFF |

## Token usage by Nemotron tier

| Model | Calls | Prompt tokens | Completion tokens | Total |
|---|---:|---:|---:|---:|
| `nvidia/Nemotron-3-Ultra-550b-a55b` | 48 | 151,665 | 728,097 | 879,762 |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | 50 | 53,879 | 233,490 | 287,369 |

Total tokens through Nebius Token Factory: **1,167,131**

## How to read this

Equivalence is not an opinion from a model. Each row means the migrated
Python produced byte-identical stdout to the GnuCOBOL-compiled original
across every listed input vector, including boundary and overflow cases
generated from the program's own PIC clauses.
