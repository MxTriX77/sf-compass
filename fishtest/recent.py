#!/usr/bin/env python3
"""What passed and failed on Fishtest since a date, from the local cache (run fishtest.py sync first).

  recent.py SINCE [section ...]     SINCE as YYYY-MM-DD; sections: counts users passed nonreg ltcfail big

counts: pass rates by bound type and TC; users: gainer STC pass rate per user; passed / nonreg:
the passed tests; ltcfail: LTC gainers that failed (most passed STC first); big: STC gainers that
failed after 150k+ games.
"""
import collections
import json
import os
import sys

CACHE = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab")) + "/fishtest/runs.jsonl"
if len(sys.argv) < 2:
    sys.exit(__doc__)
since = sys.argv[1]
sections = sys.argv[2:] or ["counts", "users", "passed", "nonreg", "ltcfail", "big"]

runs = [json.loads(l) for l in open(CACHE)]
runs = [r for r in runs if r["date"] >= since]


def tcsec(tc):
    try:
        return float(str(tc).split("+")[0].split("/")[-1])
    except ValueError:
        return 0.0


def kind(r):
    b = r["bounds"]
    if not b or b[0] is None:
        return "other"
    b = (round(b[0], 2), round(b[1], 2))
    if b == (-1.75, 0.25):
        return "nonreg"
    if b[0] >= 0:
        return "gain"
    return "other"


def tcc(r):
    s = tcsec(r["tc"])
    if s <= 12:
        return "STC"
    if s <= 70:
        return "LTC"
    return "VLTC"


def line(r):
    return f'{r["date"][5:]} {r["user"][:16]:16} {tcc(r):4} {r["games"]:>7} {r["id"][:8]} {r["branch"][:38]:38} | {r["msg"][:90]}'


fin = [r for r in runs if r["state"] in ("accepted", "rejected")]

if "counts" in sections:
    c = collections.Counter((kind(r), tcc(r), r["state"]) for r in fin)
    print(f"== finished SPRT tests since {since}: {len(fin)} (all cached runs in window: {len(runs)})")
    for k in ("gain", "nonreg"):
        for t in ("STC", "LTC", "VLTC"):
            a, rj = c[(k, t, "accepted")], c[(k, t, "rejected")]
            if a + rj:
                print(f"  {k:6} {t:4} passed {a:4} failed {rj:4}  pass rate {100 * a / (a + rj):5.1f}%")

if "users" in sections:
    print("== gainer STC by user (>= 6 finished), passed/finished")
    u = collections.defaultdict(lambda: [0, 0])
    for r in fin:
        if kind(r) == "gain" and tcc(r) == "STC":
            u[r["user"]][1] += 1
            u[r["user"]][0] += r["state"] == "accepted"
    for name, (a, n) in sorted(u.items(), key=lambda x: -x[1][1]):
        if n >= 6:
            print(f"  {name:20} {a:3}/{n:3}  {100 * a / n:5.1f}%")

if "passed" in sections:
    for t in ("STC", "LTC", "VLTC"):
        sel = [r for r in fin if kind(r) == "gain" and tcc(r) == t and r["state"] == "accepted"]
        print(f"== passed gainer {t}: {len(sel)}")
        for r in sorted(sel, key=lambda r: r["date"]):
            print("  " + line(r))

if "nonreg" in sections:
    sel = [r for r in fin if kind(r) == "nonreg" and r["state"] == "accepted"]
    print(f"== passed non-regression: {len(sel)}")
    for r in sorted(sel, key=lambda r: r["date"]):
        print("  " + line(r))

if "ltcfail" in sections:
    sel = [r for r in fin if kind(r) == "gain" and tcc(r) != "STC" and r["state"] == "rejected"]
    print(f"== failed gainer LTC/VLTC (these passed or skipped STC): {len(sel)}")
    for r in sorted(sel, key=lambda r: r["date"]):
        print("  " + line(r))

if "big" in sections:
    sel = [r for r in fin if kind(r) == "gain" and tcc(r) == "STC" and r["state"] == "rejected" and r["games"] >= 150000]
    print(f"== failed gainer STC after >= 150k games (near misses): {len(sel)}")
    for r in sorted(sel, key=lambda r: -r["games"])[:40]:
        print("  " + line(r))
