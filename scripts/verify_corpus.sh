#!/usr/bin/env bash
# Compile and run every benchmark program against its smoke fixture.
#
# No API key, no cost. Run this before `rosetta bench` - it catches a program
# that will not compile (leaving the sweep with no oracle) and lets you eyeball
# that each documented trap actually shows up in the output.
set -uo pipefail

cd "$(dirname "$0")/.."

IMAGE="${ROSETTA_SANDBOX_IMAGE:-rosetta-sandbox:latest}"

if command -v cobc >/dev/null 2>&1; then
  RUNNER=local
elif command -v docker >/dev/null 2>&1; then
  RUNNER=docker
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Sandbox image $IMAGE missing. Run: rosetta sandbox-build" >&2
    exit 2
  fi
else
  echo "Need either cobc on PATH or docker." >&2
  exit 2
fi

# SRC and IN come from the environment, so the same script body runs unchanged
# in the container and on the host.
SCRIPT='
cobc --version | head -1
echo
fail=0
for f in "$SRC"/*.cbl; do
  n=$(basename "$f" .cbl)
  if ! cobc -x -o "$TMP/$n" "$f" 2>"$TMP/$n.err"; then
    echo "COMPILE FAIL  $n"
    sed "s/^/    /" "$TMP/$n.err" | head -8
    fail=1
    continue
  fi
  if [ -f "$IN/$n.txt" ]; then
    out=$("$TMP/$n" < "$IN/$n.txt" 2>&1)
    rc=$?
  else
    out=$("$TMP/$n" < /dev/null 2>&1)
    rc=$?
    echo "NOTE          $n has no smoke fixture"
  fi
  lines=$(printf "%s\n" "$out" | wc -l | tr -d " ")
  if [ "$rc" -ne 0 ]; then
    echo "RUN FAIL      $n (exit $rc)"
    printf "%s\n" "$out" | sed "s/^/    /" | head -8
    fail=1
  elif [ -z "$out" ]; then
    echo "NO OUTPUT     $n"
    fail=1
  else
    echo "OK            $n ($lines output lines)"
  fi
done
exit $fail
'

echo "GnuCOBOL corpus check (runner: $RUNNER)"
echo

if [[ "$RUNNER" == "local" ]]; then
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  SRC="$PWD/benchmarks/programs" IN="$PWD/benchmarks/smoke" TMP="$tmp" \
    sh -c "$SCRIPT"
  status=$?
else
  docker run --rm \
    -v "$PWD/benchmarks/programs:/src:ro" \
    -v "$PWD/benchmarks/smoke:/in:ro" \
    -e SRC=/src -e IN=/in -e TMP=/tmp \
    "$IMAGE" sh -c "$SCRIPT"
  status=$?
fi

echo
if [[ $status -eq 0 ]]; then
  echo "corpus OK"
else
  echo "corpus has failures (see above)" >&2
fi
exit $status
