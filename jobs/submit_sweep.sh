#!/usr/bin/env bash
# Fan the benchmark sweep out across N Serverless AI jobs.
#
# Serverless AI jobs have NO replica or parallelism flag - one job is one
# container run. A sweep is therefore N independent submissions, each told which
# slice of the corpus it owns. run_shard.py stride-partitions on those two
# variables, so the shards stay balanced without a coordinator.
#
# Prerequisites:
#   1. Nebius AI Cloud CLI installed and configured, project ID in the profile
#   2. The job image built from Dockerfile.job and pushed to a registry the
#      project can pull from
#   3. The Token Factory key stored in SecretStash
#
# Usage:
#   ROSETTA_JOB_IMAGE=cr.eu-north1.nebius.cloud/<project>/rosetta-job:latest \
#   ROSETTA_KEY_SECRET=<secret-selector> \
#     jobs/submit_sweep.sh 8
set -euo pipefail

N="${1:-8}"

if ! command -v nebius >/dev/null 2>&1; then
  echo "nebius CLI not found. Install and configure the Nebius AI Cloud CLI first." >&2
  exit 2
fi

: "${ROSETTA_JOB_IMAGE:?set ROSETTA_JOB_IMAGE to the pushed image built from Dockerfile.job}"
: "${ROSETTA_KEY_SECRET:?set ROSETTA_KEY_SECRET to the SecretStash selector holding NEBIUS_API_KEY}"

PRESET="${ROSETTA_JOB_PRESET:-cpu-d3-4vcpu-16gb}"
PLATFORM="${ROSETTA_JOB_PLATFORM:-cpu-d3}"
BASE_URL="${NEBIUS_BASE_URL:-https://api.tokenfactory.nebius.com/v1}"
TIMEOUT="${ROSETTA_JOB_TIMEOUT:-3600s}"
RUN_TAG="${ROSETTA_RUN_TAG:-$(date +%Y%m%d-%H%M%S)}"

echo "Submitting $N shard job(s)"
echo "  image    $ROSETTA_JOB_IMAGE"
echo "  preset   $PRESET (no GPU: inference happens in Token Factory)"
echo "  run tag  $RUN_TAG"
echo

for i in $(seq 0 $((N - 1))); do
  name="rosetta-sweep-$RUN_TAG-$i"
  echo "  -> $name (shard $i of $N)"
  nebius ai job create \
    --name "$name" \
    --image "$ROSETTA_JOB_IMAGE" \
    --working-dir /app \
    --container-command "python3" \
    --args "jobs/run_shard.py" \
    --env "ROSETTA_SHARD_INDEX=$i" \
    --env "ROSETTA_SHARD_COUNT=$N" \
    --env "ROSETTA_SANDBOX=local" \
    --env "ROSETTA_PROGRAMS_DIR=benchmarks/programs" \
    --env "ROSETTA_OUTPUT_DIR=/output" \
    --env "NEBIUS_BASE_URL=$BASE_URL" \
    --env-secret "NEBIUS_API_KEY=$ROSETTA_KEY_SECRET" \
    --platform "$PLATFORM" \
    --preset "$PRESET" \
    --timeout "$TIMEOUT"
done

cat <<NOTE

Submitted $N jobs. Once they finish, pull each job's /output down into a single
directory and merge:

  python3 jobs/merge_shards.py out

The merge reads every out/shard-*.json and writes one out/report.md.
NOTE
