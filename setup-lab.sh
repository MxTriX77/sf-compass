#!/usr/bin/env bash
# One-time (idempotent) setup of the local test lab in ~/sf-lab (WSL filesystem):
# fastchess pinned to the commit Fishtest workers use, and Fishtest's default book.
set -euo pipefail

LAB=${SF_LAB:-$HOME/sf-lab}
FASTCHESS_SHA=ebfd64cb7fac80d4822c50b07dca4fe934779d21   # worker/worker.py in fishtest
BOOK=UHO_Lichess_4852_v1.epd                             # server/fishtest/views.py

mkdir -p "$LAB"/{bin,books,nets,build,runs,src}

if [[ ! -x $LAB/bin/fastchess ]]; then
  [[ -d $LAB/src/fastchess ]] || git clone -q https://github.com/Disservin/fastchess.git "$LAB/src/fastchess"
  git -C "$LAB/src/fastchess" checkout -q "$FASTCHESS_SHA"
  make -C "$LAB/src/fastchess" -j"$(nproc)" >"$LAB/src/fastchess-build.log" 2>&1
  cp "$LAB/src/fastchess/fastchess" "$LAB/bin/"
fi
"$LAB/bin/fastchess" --version

if [[ ! -f $LAB/books/$BOOK ]]; then
  curl -sSL -o "$LAB/books/$BOOK.zip" "https://github.com/official-stockfish/books/raw/master/$BOOK.zip"
  python3 -I -m zipfile -e "$LAB/books/$BOOK.zip" "$LAB/books/"
  rm "$LAB/books/$BOOK.zip"
fi
wc -l "$LAB/books/$BOOK"
