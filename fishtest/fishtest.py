#!/usr/bin/env python3
"""Read-only helper for Fishtest's public API (tests.stockfishchess.org).

  fishtest.py sync [--pages N]   cache finished tests locally, newest first
                                 (no flag: only what's new; --pages N: backfill N pages of 50)
  fishtest.py search REGEX       search cached tests by branch name and description
  fishtest.py run ID             status of one test (yours or anyone's)

Cache: $SF_LAB/fishtest/runs.jsonl (SF_LAB defaults to ~/sf-lab). The other scripts here read it.
"""
import json
import os
import re
import sys
import time
import urllib.request

API = "https://tests.stockfishchess.org/api"
CACHE = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab")) + "/fishtest/runs.jsonl"


def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "sf-compass"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def slim(run):
    a = run["args"]
    sprt = a.get("sprt") or {}
    return {
        "id": str(run["_id"]),
        "date": str(run.get("start_time", ""))[:10],
        "user": a.get("username", ""),
        "branch": a.get("new_tag", ""),
        "msg": a.get("msg_new", ""),
        "tc": a.get("tc", ""),
        "bounds": [sprt.get("elo0"), sprt.get("elo1")] if sprt else None,
        "state": sprt.get("state") or ("spsa" if a.get("spsa") else ""),
        "games": run.get("total_games") or sum(run["results"].get(k, 0) for k in ("wins", "losses", "draws")),
        "green": bool(run.get("is_green")),
    }


def load_cache():
    if not os.path.exists(CACHE):
        return []
    with open(CACHE) as f:
        return [json.loads(line) for line in f]


def sync(pages, backfill):
    """Refresh: stop at the first page with nothing new. Backfill: walk all `pages`."""
    known = {r["id"] for r in load_cache()}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    added = 0
    with open(CACHE, "a") as f:
        for page in range(1, pages + 1):
            runs = get(f"/finished_runs?page={page}")
            new = [slim(r) for r in runs.values() if str(r["_id"]) not in known]
            for r in new:
                f.write(json.dumps(r) + "\n")
            added += len(new)
            if not runs or (not new and not backfill):  # reached tests we already have
                break
            time.sleep(1)  # shared community server: stay polite
    print(f"added {added} tests; cache has {len(known) + added}")


def search(pattern):
    rx = re.compile(pattern, re.I)
    hits = [r for r in load_cache() if rx.search(r["branch"]) or rx.search(r["msg"])]
    for r in sorted(hits, key=lambda r: r["date"], reverse=True):
        verdict = "PASSED" if r["green"] else r["state"] or "?"
        print(f'{r["date"]}  {verdict:8}  {r["tc"]:8} {r["bounds"]}  {r["games"]:>7} games  '
              f'{r["user"]}/{r["branch"]}: {r["msg"][:80]}  https://tests.stockfishchess.org/tests/view/{r["id"]}')
    print(f"{len(hits)} matches")


def run(run_id):
    r = get(f"/get_run/{run_id}")
    a, res = r["args"], r["results"]
    sprt = a.get("sprt") or {}
    print(f'{a.get("username")}/{a.get("new_tag")} vs {a.get("base_tag")}  tc {a.get("tc")}  {a.get("msg_new", "")}')
    print(f'finished: {r.get("finished")}  state: {sprt.get("state") or "running"}  '
          f'bounds [{sprt.get("elo0")}, {sprt.get("elo1")}]  '
          f'LLR {sprt.get("llr", 0):.2f} ({sprt.get("lower_bound", 0):.2f}, {sprt.get("upper_bound", 0):.2f})')
    print(f'W {res.get("wins")} L {res.get("losses")} D {res.get("draws")}  '
          f'pentanomial {res.get("pentanomial")}  crashes {res.get("crashes")}  time losses {res.get("time_losses")}')


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["sync"]:
        backfill = args[1:2] == ["--pages"]
        sync(int(args[2]) if backfill else 200, backfill)
    elif args[:1] == ["search"] and len(args) == 2:
        search(args[1])
    elif args[:1] == ["run"] and len(args) == 2:
        run(args[1])
    else:
        sys.exit(__doc__)
