#!/usr/bin/env python3
"""Split a Fishtest run's result by worker: build, compiler, CPU, OS or worker name.

  by_worker.py RUN_ID [field ...]      fields from worker_info, default worker_arch
                                       (others: compiler, ARCH, uname, username, nps ...)

Useful for speed patches: a change can be faster on one build and slower on another, and an
unfiltered test averages that away. Downloads every task of the run once (0.4 s apart) into
$SF_LAB/fishtest/tasks/RUN_ID.jsonl; a run that is still going is fetched again next time.
"""
import collections
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

if len(sys.argv) < 2:
    sys.exit(__doc__)
run_id, fields = sys.argv[1], sys.argv[2:] or ["worker_arch"]
API = "https://tests.stockfishchess.org/api"
path = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab")) + f"/fishtest/tasks/{run_id}.jsonl"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sf-compass"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


if not os.path.exists(path):
    finished = get(f"{API}/get_run/{run_id}").get("finished")
    tasks, t, misses = [], 0, 0
    while misses < 3:  # task ids are dense; stop after a few missing ones
        try:
            d = get(f"{API}/get_task/{run_id}/{t}")
            if isinstance(d, dict) and "stats" in d:
                tasks.append(d)
                misses = 0
            else:
                misses += 1
        except (urllib.error.HTTPError, json.JSONDecodeError):
            misses += 1
        t += 1
        time.sleep(0.4)
    if finished:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.writelines(json.dumps(d) + "\n" for d in tasks)
else:
    tasks = [json.loads(l) for l in open(path)]


def elo(p):
    n = sum(p)
    if n == 0:
        return float("nan"), float("nan")
    s = sum(i * 0.25 * c for i, c in enumerate(p)) / n
    se = math.sqrt(sum(c * (i * 0.25 - s) ** 2 for i, c in enumerate(p)) / n / n)
    f = lambda x: -400 * math.log10(1 / x - 1) if 0 < x < 1 else float("nan")
    return f(s), (f(min(s + 1.96 * se, 0.999)) - f(max(s - 1.96 * se, 0.001))) / 2


def key(t):
    wi = t.get("worker_info", {})
    vals = []
    for f in fields:
        v = wi.get(f)
        if f == "uname" and v:
            v = v.split()[0]
        vals.append(str(v))
    return " | ".join(vals)


groups = collections.defaultdict(lambda: {"p": [0] * 5, "w": 0, "l": 0, "d": 0, "tasks": 0, "nps": []})
for t in tasks:
    st = t["stats"]
    g = groups[key(t)]
    g["p"] = [a + b for a, b in zip(g["p"], st.get("pentanomial", [0] * 5))]
    g["w"] += st["wins"]
    g["l"] += st["losses"]
    g["d"] += st["draws"]
    g["tasks"] += 1
    if t.get("worker_info", {}).get("nps"):
        g["nps"].append(t["worker_info"]["nps"])
tot = [0] * 5
print(f"{'group':52s} {'tasks':>5s} {'games':>7s} {'W':>6s} {'L':>6s} {'D':>6s}   Elo +- 95%     median bench nps")
for k, g in sorted(groups.items(), key=lambda kv: -sum(kv[1]["p"])):
    e, ci = elo(g["p"])
    games = g["w"] + g["l"] + g["d"]
    nps = sorted(g["nps"])[len(g["nps"]) // 2] if g["nps"] else 0
    tot = [a + b for a, b in zip(tot, g["p"])]
    print(f"{k[:52]:52s} {g['tasks']:5d} {games:7d} {g['w']:6d} {g['l']:6d} {g['d']:6d}  {e:+6.2f} +- {ci:4.2f}   {nps:10.0f}")
e, ci = elo(tot)
print(f"{'ALL':52s} {'':5s} {2 * sum(tot):7d} {'':20s}  {e:+6.2f} +- {ci:4.2f}")
