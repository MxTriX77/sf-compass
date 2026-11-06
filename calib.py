#!/usr/bin/env python3
"""Compass calibration: local scores next to Fishtest results, per idea.

Usage: calib.py [ledger]      (default ~/sf-lab/runs/calibration.tsv)
Ledger: tab-separated, header line first; columns
  idea   branch   local_runs (run dir names under ~/sf-lab/runs, comma-separated)   fishtest_ids (comma-separated)
Reads Fishtest only via its public API, at most one request per second; finished tests are cached in
~/sf-lab/fishtest/calib_cache.json.
"""
import json
import math
import os
import re
import sys
import time
import urllib.request

LAB = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab"))
NT = 800 / math.log(10)
CACHE = f"{LAB}/fishtest/calib_cache.json"


def stats(p):
    n = sum(p)
    s = [0, 0.25, 0.5, 0.75, 1]
    mu = sum(c * x for c, x in zip(p, s)) / n
    sd = math.sqrt(sum(c * (x - mu) ** 2 for c, x in zip(p, s)) / n)
    se = sd / math.sqrt(n)
    elo = lambda m: -400 * math.log10(1 / m - 1)
    lo, hi = elo(mu - 1.959964 * se), elo(mu + 1.959964 * se)
    nelo = NT * (mu - 0.5) / sd / math.sqrt(2)
    nci = 1.959964 * NT / math.sqrt(2) / math.sqrt(n)
    return {"elo": elo(mu), "elo_ci": (hi - lo) / 2, "nelo": nelo, "nelo_ci": nci, "games": 2 * n}


def local_ptnml(run):
    path = run if run.startswith("/") else f"{LAB}/runs/{run}"
    last = None
    for line in open(f"{path}/fastchess.log"):
        m = re.match(r"Ptnml\(0-2\): \[([\d, ]+)\]", line)
        if m:
            last = [int(x) for x in m.group(1).split(",")]
    if last is None:
        raise SystemExit(f"no pentanomial in {path}/fastchess.log")
    return last


_last_request = [0.0]


def fishtest(run_id, cache):
    if run_id in cache:
        return cache[run_id]
    wait = 1.0 - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    with urllib.request.urlopen(f"https://tests.stockfishchess.org/api/get_run/{run_id}", timeout=30) as f:
        d = json.load(f)
    _last_request[0] = time.time()
    a, sprt = d["args"], d["args"].get("sprt") or {}
    state = sprt.get("state") or ""
    status = {"accepted": "passed", "rejected": "failed"}.get(state, "stopped" if d.get("finished") else "running")
    r = {"tc": a.get("tc"), "bounds": [sprt.get("elo0"), sprt.get("elo1")], "status": status,
         "ptnml": d["results"].get("pentanomial")}
    if status != "running":
        cache[run_id] = r
    return r


def fmt(s):
    return f"nElo {s['nelo']:+.2f} ± {s['nelo_ci']:.2f} (Elo {s['elo']:+.2f} ± {s['elo_ci']:.2f}, {s['games']} games)"


def main():
    ledger = sys.argv[1] if len(sys.argv) > 1 else f"{LAB}/runs/calibration.tsv"
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    rows = [l.rstrip("\n").split("\t") for l in open(ledger)][1:]
    pairs = []  # (local nElo, STC nElo, passed) for ideas with a finished STC
    for row in rows:
        if len(row) < 4 or not row[0].strip():
            continue
        idea, branch, runs, ids = row[:4]
        ptn = [local_ptnml(r.strip()) for r in runs.split(",") if r.strip()]
        local = stats([sum(c) for c in zip(*ptn)])
        per_run = ", ".join(f"{stats(p)['nelo']:+.1f}" for p in ptn)
        print(f"#{idea} {branch}\n  local  {fmt(local)}  [per run: {per_run}]")
        stc = None
        for rid in [x.strip() for x in ids.split(",") if x.strip()]:
            r = fishtest(rid, cache)
            label = {"10+0.1": "STC", "60+0.6": "LTC"}.get(r["tc"], r["tc"])
            s = stats(r["ptnml"]) if r["ptnml"] and sum(r["ptnml"]) else None
            print(f"  {label:6} {r['status']:8} {fmt(s) if s else 'no games yet'}  bounds {r['bounds']}  {rid}")
            if label == "STC" and r["status"] != "running" and s and stc is None:
                stc = (s["nelo"], r["status"] == "passed")
        if stc:
            pairs.append((local["nelo"], *stc))
    json.dump(cache, open(CACHE, "w"))
    print("\nsummary:", end=" ")
    if not pairs:
        print("no idea has a finished STC yet")
        return
    n = len(pairs)
    print(f"{n} ideas with a finished STC, {sum(p[2] for p in pairs)} passed; "
          f"mean local nElo {sum(p[0] for p in pairs) / n:+.2f}, mean STC nElo {sum(p[1] for p in pairs) / n:+.2f}")


main()
