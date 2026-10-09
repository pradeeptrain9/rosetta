#!/usr/bin/env bash
# One-shot local setup.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env - add your NEBIUS_API_KEY before running the pipeline."
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"

echo
echo "Building the GnuCOBOL sandbox image (first run takes a minute)..."
rosetta sandbox-build

echo
echo "Setup complete. Next:"
echo "  source .venv/bin/activate"
echo "  rosetta models --resolve        # confirm which Nemotron tiers are served"
echo "  rosetta bench benchmarks/programs"
