"""Every legal successor of lf52 level 6's losing position, each labelled winnable or not.

⛔ WHY THIS EXISTS. Rule 7au set the target "make the third capture the EIGHTH candidate rather than
the first". That presumes there are candidates to rank. This enumerates them from the position
`scripts/_lf52_fate.py` proved is the last winnable one (level-6 action 123, taken from the engine),
using the offline simulator the live 91-action clear was planned from.

No engine, no harness — pure python over `scripts/_lf52_l6_model.py`, so it is cheap and repeatable.

The instrument proves itself: the position it starts from must print WINNABLE, or it is describing
some other board and every line under it is meaningless.

Expected feedback: two or more captures on offer means the ranking repair is available. ONE capture
on offer means it is not, and the applicable rule is the other one — when nothing on offer survives,
a capture is not the move.
"""
from __future__ import annotations

import importlib.util
import json
from collections import deque
from pathlib import Path

CAP = 700_000
_M = importlib.util.spec_from_file_location(
    "lf52_l6_model", Path(__file__).resolve().parent / "_lf52_l6_model.py")
L6 = importlib.util.module_from_spec(_M)
_M.loader.exec_module(L6)

# The engine's own state at level-6 action 123, recorded by scripts/_lf52_fate.py.
PADS = {(6, 6): "fozwvlovdui_red", (14, 2): "fozwvlovdui", (15, 2): "fozwvlovdui",
        (20, 7): "fozwvlovdui", (22, 5): "fozwvlovdui", (26, 3): "fozwvlovdui"}
CARTS = ((11, 6), (14, 4), (25, 2))
OX = -57


def _key(s):
    return (tuple((c, 1 if "red" in n else 0) for c, n in s[0]), s[1], s[2])


def winnable(state) -> tuple[bool, bool]:
    seen = {_key(state)}
    q = deque([state])
    n = 0
    while q:
        s = q.popleft()
        if len(s[0]) == 2:
            return True, False
        n += 1
        if n > CAP:
            return False, True
        for ns, _mv in L6.successors(s):
            k = _key(ns)
            if k not in seen:
                seen.add(k)
                q.append(ns)
    return False, False


def main() -> None:
    st = (tuple(sorted(PADS.items())), CARTS, OX)
    print(json.dumps({"control_start_winnable": winnable(st)[0]}))
    for ns, mv in L6.successors(st):
        w, c = winnable(ns)
        print(json.dumps({"mv": [str(x) for x in mv], "capture": len(ns[0]) < len(st[0]),
                          "winnable": w, "capped": c, "ox": ns[2],
                          "pads_after": sorted([list(k), v] for k, v in ns[0]),
                          "carts": [list(x) for x in ns[1]]}))


if __name__ == "__main__":
    main()
