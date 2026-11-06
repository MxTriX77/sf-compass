#!/usr/bin/env python3
"""Passed tests that never made it into Stockfish: worth a look before calling an idea new.

  unmerged.py SINCE [REF]     SINCE as YYYY-MM-DD; REF is your up-to-date Stockfish master (default: master)

Lists non-regression passes at any TC and gainer passes at LTC or longer, since SINCE, whose
branch has no test link in any commit message of REF. Nets are left out. Needs the local cache
(fishtest.py sync) and a Stockfish checkout in $SF_REPO (default ~/Stockfish).
"""
import json
import os
import subprocess
import sys

if len(sys.argv) not in (2, 3):
    sys.exit(__doc__)
since = sys.argv[1]
ref = sys.argv[2] if len(sys.argv) == 3 else "master"
LAB = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab"))
REPO = os.path.expanduser(os.environ.get("SF_REPO", "~/Stockfish"))

log = subprocess.run(["git", "-C", REPO, "log", f"--since={since}", "--format=%B", ref],
                     capture_output=True, text=True, check=True).stdout
runs = [json.loads(l) for l in open(f"{LAB}/fishtest/runs.jsonl")]
by_branch = {}
for r in runs:
    by_branch.setdefault((r["user"], r["branch"]), []).append(r)

for r in sorted(runs, key=lambda r: r["date"]):
    if r["date"] < since or r["state"] != "accepted":
        continue
    ltc = not r["tc"].startswith(("10+", "5+"))
    nonreg = r["bounds"] == [-1.75, 0.25]
    if not (ltc or nonreg) or any(k in r["branch"].lower() for k in ("nettest", "nn-", "net")):
        continue
    if any(x["id"] in log for x in by_branch[(r["user"], r["branch"])]):
        continue
    print(f"{r['date']} {r['id'][:8]} {r['user'][:16]:16} {r['branch'][:34]:34} {r['tc']:8} {r['bounds']} "
          f"{r['games']:7d} | {r['msg'][:80]}")
