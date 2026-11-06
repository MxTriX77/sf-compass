#!/usr/bin/env bash
# Counter check: how often does an idea bite? No games.
# Usage: count.sh <ref> <edit.py> [--deep-only]      (run inside WSL)
#   Exports <ref> outside the repo, runs `python3 -I <edit.py> <src dir>` to insert dbg_* counters,
#   builds without PGO at nice 19, runs `bench` and `bench 16 1 16`, prints each depth's final
#   counter report, and checks that the depth-13 node count still equals the ref's bench.
#   Convention: dbg_hit_on(..., 0) counts the nodes where the idea's new decision differs from
#   master's. Gate: SKIP when that is under 1 in 10,000 searched nodes at both depths
#   (--deep-only: at depth 16 only, for logic gated beyond bench depth).
# Exit: 0 report printed; 1 usage, edit or build failure; 3 counters changed the search.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=$HERE/build.sh
LAB=${SF_LAB:-$HOME/sf-lab}
REPO=${SF_REPO:-$HOME/Stockfish}
GATE=0.0001

usage="usage: count.sh <ref> <edit.py> [--deep-only]"
[[ $# -ge 2 && $# -le 3 ]] || { echo "$usage" >&2; exit 1; }
ref=$1
edit=$(realpath "$2")
deep_only=0
if [[ $# -eq 3 ]]; then [[ $3 == --deep-only ]] || { echo "$usage" >&2; exit 1; }; deep_only=1; fi
[[ -f $edit ]] || { echo "edit script not found: $2" >&2; exit 1; }

read -r _ ref_bench <<<"$(bash "$BUILD" "$ref")"   # validates the ref; cached after the first build
[[ -n ${ref_bench:-} ]] || { echo "could not build or bench $ref" >&2; exit 1; }

stamp="$(date +%Y%m%d-%H%M%S)-${ref//[^A-Za-z0-9._-]/_}"
mkdir -p "$LAB/count"
work="$LAB/count/$stamp.build"
report="$LAB/count/$stamp.txt"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work"
git -C "$REPO" archive "$ref" src scripts | tar -x -C "$work"
cp "$LAB"/nets/*.nnue "$work/src/"

if ! python3 -I "$edit" "$work/src"; then
  echo "edit script failed (anchor not found exactly once?): nothing built" >&2
  exit 1
fi
cd "$work/src"
if ! nice -n 19 make -j"$(nproc)" build ARCH=native >"$work/make.log" 2>&1; then
  tail -20 "$work/make.log" >&2
  echo "build failed" >&2
  exit 1
fi

# Final counter block of a bench run: the last value of each counter before "Nodes searched".
final_block() {
  awk '/^(Hit|Mean|Stdev|Extremes|Correl\.?) #[0-9]+:/ {
         k = $1 " " $2; if (!(k in v)) o[++n] = k; v[k] = $0 }
       /^Nodes searched/ { for (i = 1; i <= n; i++) print v[o[i]]; print; exit }' "$1"
}
nice -n 19 ./stockfish bench >"$work/d13.txt" 2>&1
nice -n 19 ./stockfish bench 16 1 16 >"$work/d16.txt" 2>&1

{
  echo "counter check: ref $ref (bench $ref_bench), edit $(basename "$edit")"
  for d in 13 16; do
    echo "--- depth $d"
    final_block "$work/d$d.txt"
  done
} >"$report"

nodes() { awk -F: '/^Nodes searched/ { gsub(/ /, "", $2); print $2; exit }' "$1"; }
hits0() { awk '/^Hit #0:/ { h = $6 } /^Nodes searched/ { print h; exit }' "$1"; }
n13=$(nodes "$work/d13.txt"); n16=$(nodes "$work/d16.txt")
h13=$(hits0 "$work/d13.txt"); h16=$(hits0 "$work/d16.txt")

status=0
if [[ $n13 != "$ref_bench" ]]; then
  echo "INVALID: counters changed the search (depth-13 nodes $n13, ref bench $ref_bench); numbers are invalid" >>"$report"
  status=3
elif [[ -z $h13 && -z $h16 ]]; then
  echo "GATE: none (no slot-0 counter)" >>"$report"
else
  awk -v h13="${h13:-0}" -v n13="$n13" -v h16="${h16:-0}" -v n16="$n16" -v g="$GATE" -v d="$deep_only" 'BEGIN {
    r13 = h13 / n13; r16 = h16 / n16
    printf "slot 0 (decision differs): depth 13 %d of %d nodes (%.2g), depth 16 %d of %d (%.2g)%s\n",
           h13, n13, r13, h16, n16, r16, (d ? "; deep-only: depth 16 decides" : "")
    skip = d ? (r16 < g) : (r13 < g && r16 < g)
    print (skip ? "GATE: SKIP - too rare to matter" : "GATE: PLAY") }' >>"$report"
fi
cat "$report"
echo "report: $report"
exit $status
