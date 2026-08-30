"""Can railpeg's OWN planner solve lf52 level 6 when it is handed the whole board?

⛔ Perception and planning fail the same way from the outside — the tool bids zero and the level
ends — and they want opposite repairs. This separates them with no engine in the loop at all: the
model is built from the game's own level data (`environment_files/lf52/271a04aa/lf52.py`, grid6),
handed to `railpeg` complete, and the tool's own `plan_level` / `_ensure_plan` are asked directly.

  solved TRUE at the root  -> the planner is sufficient and every remaining action is PERCEPTION
                              (map completion) or TENURE. Do not touch the search.
  solved FALSE             -> the planner is the wall, and `node_cap` / the candidate window say
                              which half of it.

CONTROLS (rule 7aj.3), printed before any verdict:
  POSITIVE  a hand-made two-green position must come back `solved` — a planner that cannot say YES
            about a solved board has measured nothing.
  NEGATIVE  the root must hold 8 pieces / 3 carts / 63 landable cells, matching the level data; and
            with the red piece NOT marked uncapturable the target set must differ, which proves the
            `noncapture` input is load-bearing rather than decorative.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ROWS = [
    "",
    " ....         ....   ",
    " .r..         .x.........>. ",
    " .x..         p..p     p |x",
    " ....         |  |    .?.|.",
    " ......       |  |    x| |",
    " ......,,-----t--3  ...L-3",
    " x.....             x",
    "   x                .",
]
GREEN, RED = 14, 8
RAIL = set("-|L3<>Tt")


def build():
    """A railpeg Model of grid6, in railpeg's own (row, col) coordinates."""
    from admorphiq.tools.railpeg import Model

    m = Model()
    m.pitch = 6
    for y, row in enumerate(ROWS):
        for x, ch in enumerate(row):
            cell = (y, x)
            if ch == " ":
                continue
            if ch in RAIL:
                m.rails.add(cell)
            elif ch == "p":
                # a stepping stone bolted to its hole: solid, and never a landing
                m.obstacles.add(cell)
            elif ch in (",", "?"):
                m.carts.add(cell)
                m.rails.add(cell)
            else:
                m.sockets.add(cell)
                if ch == "x":
                    m.pieces[cell] = GREEN
                elif ch == "r":
                    m.pieces[cell] = RED
    m.window = m.known() | m.carts
    return m


def main() -> None:
    from collections import Counter

    from admorphiq.tools.railpeg import RailPegTool, _ground, _successors, plan_level

    m = build()
    nc = frozenset({RED})
    out: dict = {
        "probe": "lf52_l6_plan",
        "ctrl_pieces": len(m.pieces),
        "ctrl_carts": len(m.carts),
        "ctrl_sockets": len(m.sockets),
        "ctrl_rails": len(m.rails),
        "ctrl_obstacles": len(m.obstacles),
        "ctrl_colours": dict(Counter(m.pieces.values())),
    }

    # POSITIVE control: two greens one jump apart is a solved board and must be reported as one.
    pos = build()
    pos.pieces = {c: v for c, v in list(pos.pieces.items()) if v == RED}
    pos.pieces[(2, 1)] = GREEN
    pos.pieces[(2, 2)] = GREEN
    got = plan_level(pos, nc, node_cap=50_000)
    out["ctrl_positive_solved"] = bool(got and got[1])

    # NEGATIVE control: the noncapture input must change what the planner is aiming at.
    out["ctrl_noncapture_matters"] = (
        plan_level(build(), frozenset(), node_cap=2000) != plan_level(build(), nc, node_cap=2000))

    for cap in (90_000, 400_000, 2_000_000):
        t0 = time.time()
        got = plan_level(build(), nc, node_cap=cap)
        out[f"root_{cap}"] = {
            "found": got is not None,
            "solved": bool(got and got[1]),
            "moves": None if got is None else len(got[0]),
            "secs": round(time.time() - t0, 1),
        }

    # The tool's own decision loop, with nothing hidden from it.
    tool = RailPegTool()
    tool.reset()
    tool._noncapture = nc
    mm = build()
    tool._model = mm
    tool._touched = set(mm.pieces)
    tool._ntouched = len(tool._touched)
    tool._peaked = len(mm.pieces)
    trace: list[dict] = []
    won = False
    for step in range(400):
        greens = sum(1 for v in mm.pieces.values() if v == GREEN)
        if greens <= 1:
            won = True
            break
        if not tool._plan:
            bid = tool._ensure_plan(mm)
            if not bid:
                trace.append({"step": step, "bid": 0.0, "greens": greens,
                              "why": dict(Counter(tool._why).most_common(6))})
                break
        if not tool._plan:
            break
        mv = tool._plan.pop(0)
        legal = any(x == mv for _ns, x, _c in _successors(mm.state(), _ground(mm), nc))
        if not legal:
            trace.append({"step": step, "illegal": list(mv), "greens": greens})
            tool._plan = []
            continue
        tool._advance(mm, mv)
        if len(trace) < 80:
            trace.append({"step": step, "mv": [mv[0], mv[1], mv[2]], "greens": greens})
    out["loop_won"] = won
    out["loop_steps"] = len(trace)
    out["loop_greens_end"] = sum(1 for v in mm.pieces.values() if v == GREEN)
    out["loop_tiers"] = dict(tool._tiers)
    out["loop_why"] = dict(Counter(tool._why).most_common(12))
    out["loop_tail"] = trace[-10:]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
