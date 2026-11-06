#!/usr/bin/env python3
"""Elo, nElo and normalized-SPRT LLR (normal approximation) from pentanomial counts.

Usage: penta_llr.py [--elo0 E0] [--elo1 E1] "a,b,c,d,e" ["a,b,c,d,e" ...]   (several are summed)
Bounds are in nElo: quick run -8 0 (default), deep run 0 3, direction run -5 5.
Use it to combine an interrupted run with its top-up. Reproduces fastchess's Elo and nElo
(± 95% error) exactly and its LLR to about ±0.01.
"""
import argparse
import math

NT = 800 / math.log(10)  # nElo per unit t-value


def summary(p, elo0, elo1):
    n = sum(p)
    s = [0, 0.25, 0.5, 0.75, 1]
    mu = sum(c * x for c, x in zip(p, s)) / n
    var = sum(c * (x - mu) ** 2 for c, x in zip(p, s)) / n
    sd = math.sqrt(var)
    se = sd / math.sqrt(n)
    elo = lambda m: -400 * math.log10(1 / m - 1)
    t = (mu - 0.5) / sd
    nelo = NT * t / math.sqrt(2)
    nelo_ci = 1.959964 * NT / math.sqrt(2) / math.sqrt(n)
    t0, t1 = elo0 * math.sqrt(2) / NT, elo1 * math.sqrt(2) / NT
    llr = n * (t1 - t0) * (2 * t - t0 - t1) / 2
    lo, hi = elo(mu - 1.959964 * se), elo(mu + 1.959964 * se)
    return (f"games {2 * n}  Elo {elo(mu):+.2f} +/- {(hi - lo) / 2:.2f}  "
            f"nElo {nelo:+.2f} +/- {nelo_ci:.2f}  LLR {llr:.2f} [{elo0:g}, {elo1:g}]")


ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--elo0", type=float, default=-8.0)
ap.add_argument("--elo1", type=float, default=0.0)
ap.add_argument("ptnml", nargs="+", help='pentanomial "a,b,c,d,e" (brackets and spaces are fine)')
a = ap.parse_args()
parts = [[int(x) for x in s.strip("[] ").replace(" ", "").split(",")] for s in a.ptnml]
total = [sum(col) for col in zip(*parts)]
if len(parts) > 1:
    for p in parts:
        print("part :", summary(p, a.elo0, a.elo1))
print("total:", summary(total, a.elo0, a.elo1))
