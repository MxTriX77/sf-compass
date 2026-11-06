#!/usr/bin/env python3
"""Details of Fishtest runs: Elo and nElo from the pentanomial, the Info text, and optionally the diff.

  runinfo.py [--diff] ID_OR_PREFIX ...      a short prefix is resolved through the local cache

The diff comes from GitHub's public compare API (no login, 60 requests an hour).
"""
import json
import math
import os
import sys
import urllib.request

CACHE = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab")) + "/fishtest/runs.jsonl"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
want_diff = "--diff" in sys.argv
if not args:
    sys.exit(__doc__)
ids = {}
if any(len(a) < 24 for a in args) and os.path.exists(CACHE):
    for line in open(CACHE):
        r = json.loads(line)
        for a in args:
            if r["id"].startswith(a):
                ids[a] = r["id"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sf-compass"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def elo(x):
    return -400 * math.log10(1 / x - 1)


for a in args:
    rid = ids.get(a, a)
    try:
        r = get(f"https://tests.stockfishchess.org/api/get_run/{rid}")
    except Exception as e:  # noqa: BLE001
        print(f"{a}: {e}")
        continue
    ar, res = r["args"], r.get("results", {})
    p = res.get("pentanomial", [0] * 5)
    n = sum(p)
    line = f'{rid[:8]} {ar.get("username")}/{ar.get("new_tag")} tc {ar.get("tc")} th {ar.get("threads")}'
    sprt = ar.get("sprt") or {}
    if sprt:
        line += f' bounds [{sprt.get("elo0")}, {sprt.get("elo1")}] LLR {sprt.get("llr", 0):.2f} {sprt.get("state", "")}'
    if n:
        s = [0, 0.5, 1, 1.5, 2]
        mean = sum(x * y for x, y in zip(s, p)) / n
        var = sum(y * (x - mean) ** 2 for x, y in zip(s, p)) / n
        sc, se = mean / 2, math.sqrt(var / n) / 2
        nelo = (mean - 1) / math.sqrt(var) * (800 / math.log(10)) / math.sqrt(2) if var else 0
        line += f' | games {2 * n} Elo {elo(sc):+.2f} +- {(elo(sc + 1.96 * se) - elo(sc - 1.96 * se)) / 2:.2f} nElo {nelo:+.2f} penta {p}'
    print(line)
    print("   info:", (ar.get("info") or "").replace("\n", " / ")[:500])
    base, new, repo = ar.get("resolved_base", ""), ar.get("resolved_new", ""), ar.get("tests_repo", "")
    print(f"   base {base[:10]} new {new[:10]} {repo}")
    if want_diff and base and new and "github.com/" in repo:
        slug = repo.split("github.com/")[1].strip("/")
        try:
            cmp = get(f"https://api.github.com/repos/{slug}/compare/{base}...{new}")
            print("\n".join(f"--- {f['filename']}\n{f.get('patch', '')}" for f in cmp.get("files", []))[:6000])
        except Exception as e:  # noqa: BLE001
            print(f"   diff: {e}")
