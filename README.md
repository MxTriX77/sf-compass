# sf-compass

Scripts to test Stockfish ideas on one machine before you spend Fishtest time on them.

Fishtest decides. This helps you decide where to point it. Not just pass/fail:
- does an idea even change anything? (count.sh, ~10 min, no games)
- which way should a value move? (sandbox.sh --direction)
- is a patch broken or clearly worse? (sandbox.sh, ~80 min)
- does it look like a real gain? (sandbox.sh --deep, overnight)

## What's in it

- count.sh - counter check, no games. Adds dbg counters to bench and tells you how
  often your change actually changes a decision. ~10 min. Start your edit from
  count-template.py.
- sandbox.sh - patch vs base with fastchess, set up like Fishtest (same book, paired
  games, pentanomial, nElo SPRT).
  - default: quick run, ~80 min. Broken or clearly worse?
  - --deep: overnight, up to 32k games. Does it look like a gain?
  - --direction: two variants of a constant against each other. Which way should it move?
- build.sh - builds a commit with profile-build, cached, and prints its bench.
- penta_llr.py - combines an interrupted run with its top-up.
- calib.py - puts your local results next to your Fishtest results.

## Setup

Linux or WSL, a C++ compiler, git, python3.

    ./setup-lab.sh

Builds fastchess at the commit Fishtest uses and gets Fishtest's default book, all in ~/sf-lab.

## Use

    SF_REPO=~/Stockfish ./sandbox.sh master my-branch

Both refs must be committed. One match runs at a time, others wait in line.
Env settings: SF_TC (5+0.05), SF_CONCURRENCY (14), SF_MAX_GAMES, SF_ELO0/SF_ELO1, SF_LAB, SF_REPO.

## Numbers

Calibrated on one laptop (Ryzen 7 7735HS): ~3000 games/h at 5+0.05 with 14 games at once,
+-5.6 Elo at the 4000 game cap. Yours will differ, check with:

    SF_MAX_GAMES=600 ./sandbox.sh master master --same-ok

It can't see small gains. Typical Stockfish gains today are +1 to +3 Elo, way below what
one PC resolves in an hour. A SEND means "worth a Fishtest test", nothing more.

## License

GPLv3
