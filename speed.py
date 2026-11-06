#!/usr/bin/env python3
"""Paired bench speed comparison of two Stockfish binaries: base vs patch.

usage: speed.py BASE_BIN PATCH_BIN [--pairs N] [--mode par|seq] [--cores A,B] [--bench "16 1 13"]

par (default): each pair runs base and patch at the same time, on the two halves of --cores,
               swapped every pair, so load from the rest of the PC hits both equally.
               --cores 0,2,4,6,8,10,12,14 runs 4 + 4 at once, closer to a busy Fishtest worker.
seq:           each pair runs base and patch one after the other on the first core.
Both binaries must search the same tree (same bench node count), or it stops.
Holds $SF_LAB/sandbox.lock while measuring, so no sandbox match runs meanwhile.
"""
import argparse
import fcntl
import math
import os
import random
import re
import statistics
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("base")
ap.add_argument("patch")
ap.add_argument("--pairs", type=int, default=20)
ap.add_argument("--mode", choices=["seq", "par"], default="par")
ap.add_argument("--cores", default="2,6")
ap.add_argument("--bench", default="16 1 13")
ap.add_argument("--out", default=None, help="write the per-pair numbers to this TSV file")
a = ap.parse_args()
cores = a.cores.split(",")

LAB = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab"))
os.makedirs(LAB, exist_ok=True)
lock = open(f"{LAB}/sandbox.lock", "w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("waiting for sandbox.lock (a match is running)", file=sys.stderr, flush=True)
    fcntl.flock(lock, fcntl.LOCK_EX)


def start(binary, core):
    return subprocess.Popen(["taskset", "-c", core, binary, "bench", *a.bench.split()],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def result(p):
    err = p.communicate()[1]
    nodes = int(re.search(r"Nodes searched\s*:\s*(\d+)", err).group(1))
    nps = int(re.search(r"Nodes/second\s*:\s*(\d+)", err).group(1))
    return nodes, nps


rows, ratios = [], []
first = random.randrange(2)
for i in range(a.pairs):
    flip = (i + first) % 2 == 1  # strict alternation cancels per-core speed differences
    if a.mode == "seq":
        order = [("patch", a.patch), ("base", a.base)] if flip else [("base", a.base), ("patch", a.patch)]
        res = {name: result(start(b, cores[0])) for name, b in order}
    else:
        h = len(cores) // 2
        cb, cp = (cores[h:], cores[:h]) if flip else (cores[:h], cores[h:])
        procs = [(start(a.base, c), "base") for c in cb] + [(start(a.patch, c), "patch") for c in cp]
        out = {"base": [], "patch": []}
        for p, name in procs:
            out[name].append(result(p))
        res = {k: (v[0][0], sum(x[1] for x in v) // len(v)) for k, v in out.items()}
    (nb, sb), (np_, sp) = res["base"], res["patch"]
    if nb != np_:
        sys.exit(f"node counts differ: base {nb} patch {np_} -> functional change, stop")
    r = sp / sb - 1
    ratios.append(r)
    rows.append((i, sb, sp, r, flip))
    print(f"pair {i + 1:3d}/{a.pairs}: base {sb:8d} patch {sp:8d}  {r * 100:+6.2f}%", flush=True)

n = len(ratios)
m = statistics.mean(ratios)
sd = statistics.stdev(ratios)
# two-sided 95% t quantiles for small n, else 1.96
tq = {5: 2.776, 10: 2.262, 15: 2.145, 20: 2.093, 30: 2.045, 40: 2.023, 60: 2.001}
t = next((v for k, v in sorted(tq.items()) if n - 1 < k), 1.96) if n < 61 else 1.96
ci = t * sd / math.sqrt(n)
pgt0 = 0.5 * (1 + math.erf(m / (sd / math.sqrt(n)) / math.sqrt(2)))
print(f"\nResult of {n} pairs ({a.mode}, bench {a.bench}, cores {a.cores})")
print(f"base  nps mean {statistics.mean(x[1] for x in rows):10.0f}   patch nps mean {statistics.mean(x[2] for x in rows):10.0f}")
print(f"speedup = {m * 100:+.3f}% +/- {ci * 100:.3f}% (95% CI)   median {statistics.median(ratios) * 100:+.3f}%   "
      f"sd per pair {sd * 100:.2f}%")
print(f"P(speedup > 0) = {pgt0:.4f}")
if a.out:
    with open(a.out, "w") as f:
        f.write("pair\tbase_nps\tpatch_nps\tratio\tswapped\n")
        for r_ in rows:
            f.write("\t".join(map(str, r_)) + "\n")
