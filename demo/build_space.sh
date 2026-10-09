#!/usr/bin/env bash
# Assemble a Hugging Face Space payload from this repository.
#
# A Space wants Dockerfile and the frontmatter README.md at its ROOT, while this
# repo keeps them under demo/ so they do not collide with the project's own
# Dockerfile and README. Rather than contort the repo layout for one deploy
# target, this stages a directory with the layout a Space expects.
#
# The Dockerfile's COPY paths are relative to the build context, so the staged
# tree keeps the same relative shape (demo/, rosetta/, benchmarks/).
#
#   demo/build_space.sh [staging_dir]
set -euo pipefail

cd "$(dirname "$0")/.."
STAGE="${1:-build/space}"

if [[ ! -d demo/precomputed ]] || [[ ! -f demo/precomputed/index.json ]]; then
  echo "demo/precomputed is missing or empty." >&2
  echo "Run: rosetta bench benchmarks/programs && python3 demo/precompute.py" >&2
  exit 2
fi

rm -rf "$STAGE"
mkdir -p "$STAGE"

# Root-level files the Space platform requires.
cp demo/Dockerfile "$STAGE/Dockerfile"
cp demo/README.md  "$STAGE/README.md"
cp pyproject.toml  "$STAGE/pyproject.toml"

# Application tree, same relative paths the Dockerfile COPYs.
mkdir -p "$STAGE/demo"
cp demo/app.py demo/requirements.txt "$STAGE/demo/"
cp -r demo/precomputed "$STAGE/demo/precomputed"
cp -r rosetta "$STAGE/rosetta"
cp -r benchmarks "$STAGE/benchmarks"

# Keep the image lean and never ship local state.
rm -rf "$STAGE"/rosetta/__pycache__ "$STAGE"/demo/__pycache__
find "$STAGE" -name '.DS_Store' -delete

cat > "$STAGE/.gitignore" <<'IGNORE'
__pycache__/
*.pyc
.env
IGNORE

# pyproject's readme points at README.md, which in the Space is the HF card.
# That is harmless for `pip install -e .` and keeps the card at the root where
# the platform looks for it.

echo "staged Space payload in $STAGE"
echo
echo "contents:"
( cd "$STAGE" && find . -maxdepth 2 -not -path '*/precomputed/*' | sort | sed 's|^\./||' | sed '/^$/d' )
echo
programs=$(python3 -c "import json;print(len(json.load(open('$STAGE/demo/precomputed/index.json'))))")
echo "pre-computed programs: $programs"
