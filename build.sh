#!/usr/bin/env bash
# Build Stockfish at a git ref, cached by commit, and print "<binary> <bench>".
# Usage: build.sh <git-ref>      (run inside WSL)
# The build happens on the WSL filesystem (fast), never in the repo checkout.
set -euo pipefail

REPO=${SF_REPO:-$HOME/Stockfish}
LAB=${SF_LAB:-$HOME/sf-lab}
ref=${1:?usage: build.sh <git-ref>}

# Cache by source tree, not commit: amending only the message (to add the Bench line) reuses the build.
sha=$(git -C "$REPO" rev-parse --verify --quiet "$ref^{tree}") || { echo "unknown ref: $ref" >&2; exit 1; }
id=${sha:0:12}
bin="$LAB/bin/sf-$id"
mkdir -p "$LAB/bin" "$LAB/build" "$LAB/nets"

# One build per commit at a time, even if several sessions ask for it.
exec 8>"$LAB/build/$id.lock"
flock 8

if [[ ! -x $bin ]]; then
  src="$LAB/build/$id"
  rm -rf "$src" && mkdir -p "$src"
  git -C "$REPO" archive "$sha" | tar -x -C "$src"
  # Reuse cached nets so each build doesn't download ~100 MB again.
  for net in $(grep -oh 'nn-[0-9a-f]\{12\}\.nnue' "$src"/src/evaluate.h | sort -u); do
    [[ -f $LAB/nets/$net ]] && cp "$LAB/nets/$net" "$src/src/"
  done
  # nice: a build must not steal CPU from a sandbox match that may be running.
  if ! nice -n 19 make -C "$src/src" -j"$(nproc)" profile-build ARCH=native >"$src/build.log" 2>&1; then
    tail -30 "$src/build.log" >&2
    echo "build failed for $ref ($id); full log: $src/build.log" >&2
    exit 1
  fi
  cp -n "$src"/src/nn-*.nnue "$LAB/nets/" 2>/dev/null || true
  cp "$src/src/stockfish" "$bin.tmp" && mv "$bin.tmp" "$bin"
  rm -rf "$src"
fi

# Bench = node count of the standard bench run: the patch's fingerprint on Fishtest.
if [[ ! -s $bin.bench ]]; then
  "$bin" bench 2>&1 | awk '/Nodes searched/ {print $4}' >"$bin.bench"
fi
echo "$bin $(cat "$bin.bench")"
