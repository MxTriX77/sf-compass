#!/usr/bin/env bash
# Local filter: play <patch> against <base> and print a verdict.
# Usage: sandbox.sh <base-ref> <patch-ref> [--same-ok] [--deep | --direction]   (run inside WSL)
#   default      quick run: does the patch look broken or clearly worse?   ~80 min
#   --deep       deep run: does the patch look like a real gain?           up to ~11 h
#   --direction  base = "minus" variant, patch = "plus" variant: which way should the change go?
# Only one match runs at a time; other callers wait in line (flock).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=$HERE/build.sh
LAB=${SF_LAB:-$HOME/sf-lab}

usage="usage: sandbox.sh <base-ref> <patch-ref> [--same-ok] [--deep | --direction]"
if [[ $# -lt 2 ]]; then echo "$usage" >&2; exit 1; fi
base_ref=$1
patch_ref=$2
shift 2
same_ok=0
mode=quick
for arg in "$@"; do
  case $arg in
    --same-ok) same_ok=1 ;;
    --deep)      [[ $mode == quick ]] || { echo "$usage" >&2; exit 1; }; mode=deep ;;
    --direction) [[ $mode == quick ]] || { echo "$usage" >&2; exit 1; }; mode=direction ;;
    *) echo "$usage" >&2; exit 1 ;;
  esac
done

# Presets per mode (nElo bounds, game cap); environment variables still win.
case $mode in
  quick)     d_elo0=-8; d_elo1=0; d_games=4000 ;;   # [-8, 0] nElo ~ [-4, 0] Elo; ~80 min
  deep)      d_elo0=0;  d_elo1=3; d_games=32000 ;;  # gainer filter; ~11 h
  direction) d_elo0=-5; d_elo1=5; d_games=4000 ;;   # symmetric: which side is better
esac
TC=${SF_TC:-5+0.05}                    # half of Fishtest STC (10+0.1): ~2x the games per hour
HASH=${SF_HASH:-16}
CONCURRENCY=${SF_CONCURRENCY:-14}      # 16 threads minus 2 for the rest of the PC
MAX_GAMES=${SF_MAX_GAMES:-$d_games}    # ~3000 games/h (calibrated, see README)
ELO0=${SF_ELO0:-$d_elo0}               # nElo, the same Elo model Fishtest uses
ELO1=${SF_ELO1:-$d_elo1}
BOOK=$LAB/books/UHO_Lichess_4852_v1.epd

base_out=$(bash "$BUILD" "$base_ref")
patch_out=$(bash "$BUILD" "$patch_ref")
read -r base_bin base_bench <<<"$base_out"
read -r patch_bin patch_bench <<<"$patch_out"
echo "base : $base_ref  bench $base_bench"
echo "patch: $patch_ref  bench $patch_bench"
if [[ $base_bench == "$patch_bench" && $same_ok -eq 0 ]]; then
  echo "VERDICT: SKIP - same bench, so the patch does not change how the engine plays."
  echo "Non-functional change: measure speed instead of Elo."
  exit 2
fi

run="$LAB/runs/$(date +%Y%m%d-%H%M%S)-${patch_ref//[^A-Za-z0-9._-]/_}"
mkdir -p "$run"

exec 9>"$LAB/sandbox.lock"
if ! flock -n 9; then
  echo "Sandbox busy with another match; waiting in line..."
  flock 9
fi

echo "Playing up to $MAX_GAMES games at $TC, $CONCURRENCY at a time ($mode run, bounds [$ELO0, $ELO1] nElo). Progress: $run/fastchess.log"
start=$(date +%s)
cd "$run"   # fastchess writes its files to the working dir; keep them out of the repo
set +e
"$LAB/bin/fastchess" \
  -engine cmd="$patch_bin" name=patch -engine cmd="$base_bin" name=base \
  -each proto=uci tc="$TC" option.Hash="$HASH" option.Threads=1 \
  -openings file="$BOOK" format=epd order=random -repeat -games 2 -rounds $((MAX_GAMES / 2)) \
  -concurrency "$CONCURRENCY" -report penta=true -check-mate-pvs \
  -draw movenumber=34 movecount=8 score=20 \
  -sprt elo0="$ELO0" elo1="$ELO1" alpha=0.05 beta=0.05 model=normalized \
  -ratinginterval 200 -scoreinterval 0 -autosaveinterval 0 -pgnout file="$run/games.pgn" \
  >"$run/fastchess.log" 2>&1
status=$?
set -e
minutes=$(( ($(date +%s) - start) / 60 ))

log=$run/fastchess.log
elo=$(grep '^Elo:' "$log" | tail -1 || true)
los=$(grep '^LOS:' "$log" | tail -1 | sed -E 's/,.*//' || true)
games=$(grep '^Games:' "$log" | tail -1 | sed -E 's/^Games: ([0-9]+).*/\1/' || true)
llr_line=$(grep '^LLR:' "$log" | tail -1 || true)
read -r llr lo hi < <(sed -E 's/^LLR: (-?[0-9.]+) .*\((-?[0-9.]+), (-?[0-9.]+)\).*/\1 \2 \3/' <<<"$llr_line")
# fastchess's end summary prints "Crashed: 0" per player whenever a player had a timeout: not a crash.
broken=$(grep -i -E 'illegal move|disconnect|crash' "$log" | grep -c -v -E '^[[:space:]]*Crashed: 0[[:space:]]*$' || true)
timeouts=$(grep -c 'on time' "$log" || true)

if [[ $status -ne 0 || -z $llr_line || $broken -gt 0 ]]; then
  line="VERDICT: DROP - broken: engine crashed, made an illegal move, or fastchess failed (exit $status)"
  row="DROP"
else
  read -r row line < <(awk -v l="$llr" -v lo="$lo" -v hi="$hi" -v m="$mode" -v los="$los" 'BEGIN {
    e = (l <= lo) ? "low" : (l >= hi) ? "high" : (l < 0) ? "lean-low" : "lean-high"
    if (m == "quick") {
      if (e == "low")       print "DROP VERDICT: DROP - clearly worse (stopped early)"
      else if (e == "high") print "SEND VERDICT: SEND - clearly not worse (stopped early)"
      else if (e == "lean-low") print "DROP VERDICT: DROP - time is up, results lean worse"
      else                  print "SEND VERDICT: SEND - time is up, not clearly worse"
    } else if (m == "deep") {
      if (e == "low")       print "DROP(deep) VERDICT: DROP - no gain (stopped early)"
      else if (e == "high") print "SEND(deep) VERDICT: SEND - likely gain (stopped early)"
      else if (e == "lean-low") print "DROP(deep) VERDICT: DROP - time is up, no clear gain"
      else                  print "SEND(deep) VERDICT: SEND - time is up, leans gain"
    } else {
      if (e == "low")       print "DIRECTION-minus DIRECTION: minus (stopped early), " los
      else if (e == "high") print "DIRECTION-plus DIRECTION: plus (stopped early), " los
      else if (e == "lean-low") print "DIRECTION-minus DIRECTION: leans minus, " los
      else                  print "DIRECTION-plus DIRECTION: leans plus, " los
    } }')
fi

echo "----"
echo "$line"
echo "$elo"
echo "games: ${games:-0} in ${minutes} min, time losses: $timeouts, ${llr_line}"
[[ ${games:-0} -gt 0 && $timeouts -gt $(( games / 100 )) ]] && echo "WARNING: over 1% of games lost on time; the PC may be overloaded."
echo "log: $log"

printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -Is)" "$base_ref" "$base_bench" "$patch_ref" "$patch_bench" \
  "${games:-0}" "$elo" "$llr" "$row" "$run" >>"$LAB/runs/index.tsv"
