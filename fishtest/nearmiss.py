#!/usr/bin/env python3
"""STC gainer tests that were stopped without an SPRT decision while trending positive.

  nearmiss.py SINCE          SINCE as YYYY-MM-DD; reads the local cache (fishtest.py sync first)

Fetches each candidate's pentanomial once (1 request per second, cached in
$SF_LAB/fishtest/nearmiss_cache.json) and lists the 40 with the highest LLR, nElo with 95% CI.
"""
import json
import math
import os
import sys
import time
import urllib.request

if len(sys.argv) != 2:
    sys.exit(__doc__)
since = sys.argv[1]
LAB = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab"))
NT = 800 / math.log(10)
rows = [json.loads(l) for l in open(f"{LAB}/fishtest/runs.jsonl")]
sel = [r for r in rows if r["state"] == "" and r["date"] >= since and r["tc"] == "10+0.1"
       and r["bounds"] == [0.0, 2.0] and r["games"] >= 4000]
print(f"stopped STC gainers with >= 4000 games since {since}: {len(sel)}", flush=True)
cache_p = f"{LAB}/fishtest/nearmiss_cache.json"
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
for r in sel:
    if r["id"] in cache:
        continue
    try:
        req = urllib.request.Request(f"https://tests.stockfishchess.org/api/get_run/{r['id']}",
                                     headers={"User-Agent": "sf-compass"})
        with urllib.request.urlopen(req, timeout=30) as f:
            d = json.load(f)
        cache[r["id"]] = {"ptnml": d["results"].get("pentanomial"), "llr": (d["args"].get("sprt") or {}).get("llr"),
                          "finished": d.get("finished")}
    except Exception as e:  # noqa: BLE001
        print("err", r["id"], e, flush=True)
    time.sleep(1)
json.dump(cache, open(cache_p, "w"))
out = []
for r in sel:
    c = cache.get(r["id"])
    if not c or not c["ptnml"] or not sum(c["ptnml"]) or not c["finished"]:
        continue
    p = c["ptnml"]
    n = sum(p)
    s = [0, .25, .5, .75, 1]
    mu = sum(a * b for a, b in zip(p, s)) / n
    sd = math.sqrt(sum(a * (b - mu) ** 2 for a, b in zip(p, s)) / n)
    nelo = NT * (mu - 0.5) / sd / math.sqrt(2)
    ci = 1.96 * NT / math.sqrt(2) / math.sqrt(n)
    out.append((c["llr"] or 0, nelo, ci, 2 * n, r))
out.sort(key=lambda x: -x[0])
for llr, nelo, ci, g, r in out[:40]:
    if llr < 0.8:
        break
    print(f"LLR {llr:+.2f}  nElo {nelo:+.1f} +- {ci:.1f}  {g:6d} games  {r['date']}  {r['user']}/{r['branch']}: "
          f"{r['msg'][:80]}  {r['id']}")
