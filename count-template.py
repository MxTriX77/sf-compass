#!/usr/bin/env python3
"""Counter edit for count.sh. Copy to ~/sf-lab/count/edits/<idea>.py and fill in the patches.

Called as `python3 -I <edit.py> <src dir>` on a throwaway export of the ref (usually master).
Rules:
- Only observe the search: compute the idea's new decision next to master's and count; never change
  what the search does (count.sh checks the node count against the ref's bench).
- Slot 0, dbg_hit_on(<new decision differs from master's>, 0), is the gate counter: count.sh compares
  its hits with the nodes searched. Use slots 1+ and dbg_mean_of/... for anything else useful.
- Each anchor must occur exactly once (patch() asserts it), so a moved upstream line fails loudly.

Example: unify-corr-div (futility term with /198368 instead of /198435), on master ff7cee42.
"""
import sys

SRC = sys.argv[1]


def patch(path, old, new):
    p = f"{SRC}/{path}"
    s = open(p).read()
    n = s.count(old)
    assert n == 1, f"{path}: anchor found {n} times: {old[:70]!r}"
    open(p, "w").write(s.replace(old, new))


patch("search.cpp",
      """        if (eval - futilityMargin >= beta)
            return (661 * beta + 363 * eval) / 1024;""",
      """        {
            const int oldT = std::abs(correctionValue) / 198435;
            const int newT = std::abs(correctionValue) / 198368;
            dbg_hit_on((eval - futilityMargin >= beta)
                         != (eval - (futilityMargin - oldT + newT) >= beta), 0);
            dbg_hit_on(oldT != newT, 1);
        }
        if (eval - futilityMargin >= beta)
            return (661 * beta + 363 * eval) / 1024;""")
