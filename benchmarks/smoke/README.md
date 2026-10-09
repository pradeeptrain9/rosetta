# Smoke inputs

One stdin fixture per benchmark program, chosen so the program's documented
trap is actually reachable. `scripts/verify_corpus.sh` compiles every program
with GnuCOBOL and runs it against its fixture.

This is the cheap gate to run before `rosetta bench`: it needs no API key and
costs nothing, and it catches the two failures that would otherwise waste a
full sweep — a program that does not compile (no oracle) and a program whose
trap never fires (equivalence proven trivially).

Note on scaled input: `ACCEPT` into a `V`-scaled numeric field reads stdin as
an integer, so `0500` into `PIC 9(2)V99` lands as zero, not 5.00. Programs that
need a fraction therefore take an integer (basis points, thousandths) and scale
it with `COMPUTE`. Fixtures follow that convention.
