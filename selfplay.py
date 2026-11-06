#!/usr/bin/env python3
"""Counters in real games: play an instrumented Stockfish build against itself with real clocks.

usage: selfplay.py BIN [--threads 1] [--tc 10+0.1] [--games 20] [--hash 16]

bench never stops a search early and never uses time management or more than one thread, so
count.sh can't see code that only runs there (time management, stopped searches, helper
threads). This plays BIN against itself from random openings of Fishtest's book, with real
clocks, and prints the dbg_hit_on / dbg_mean_of counters after every game.

BIN needs your counters, and preferably `dbg_print();` right before the `bestmove` line in
search.cpp, so the counters are printed after every move (otherwise only once a second).
Games end at mate, stalemate, a lost clock or 200 plies (no draw or resign adjudication).
Python adds a little latency per move, so short time controls lose some games on time:
fine for counting, not for measuring Elo.
"""
import argparse
import os
import random
import re
import subprocess
import time

ap = argparse.ArgumentParser()
ap.add_argument("bin")
ap.add_argument("--threads", type=int, default=1)
ap.add_argument("--tc", default="10+0.1", help="base+increment in seconds")
ap.add_argument("--games", type=int, default=20)
ap.add_argument("--hash", type=int, default=16)
a = ap.parse_args()
base, inc = (float(x) for x in a.tc.split("+"))

LAB = os.path.expanduser(os.environ.get("SF_LAB", "~/sf-lab"))
book = [l.split(";")[0].strip() for l in open(f"{LAB}/books/UHO_Lichess_4852_v1.epd") if l.strip()]
p = subprocess.Popen([a.bin], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, bufsize=1)  # dbg_print writes to stderr
counters = {}  # "Hit #0" -> its latest line


def send(s):
    p.stdin.write(s + "\n")
    p.stdin.flush()


def wait_for(prefix):
    while True:
        line = p.stdout.readline()
        if not line:
            raise SystemExit("engine died")
        m = re.match(r"(\w+ #\d+):", line)
        if m:
            counters[m.group(1)] = line.strip()
        if line.startswith(prefix):
            return line


send("uci")
wait_for("uciok")
send(f"setoption name Threads value {a.threads}")
send(f"setoption name Hash value {a.hash}")
moves_total = 0
for g in range(a.games):
    fen = random.choice(book)
    send("ucinewgame")
    send("isready")
    wait_for("readyok")
    clock = [base * 1000, base * 1000]
    moves = []
    for ply in range(200):
        side = ply % 2
        send("position fen " + fen + (" moves " + " ".join(moves) if moves else ""))
        t0 = time.time()
        send(f"go wtime {int(clock[0])} btime {int(clock[1])} winc {int(inc * 1000)} binc {int(inc * 1000)}")
        best = wait_for("bestmove").split()[1]
        clock[side] += inc * 1000 - (time.time() - t0) * 1000
        moves_total += 1
        if best == "(none)" or clock[side] < 0:
            break
        moves.append(best)
    print(f"game {g + 1}/{a.games}: {len(moves)} plies, {moves_total} moves searched so far")
    for k in sorted(counters):
        print("  " + counters[k])
send("quit")
