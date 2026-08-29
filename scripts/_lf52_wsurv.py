"""lf52 level 6 — on a WIDE map, is there any rule `pegjump` could apply that avoids the loss?

⛔ WHAT IS ALREADY MEASURED, so this probe does not re-ask it.
  * `scripts/_lf52_pcen.py`: the four missing pads are lost to the CAMERA and nothing else — 14
    socket squares in the frame and exactly 2 discs, `off_phase_discs` 0, `disc_colour_refused` 0,
    `model_pieces_peak` 2 for the whole level. No filter drops anything and nothing is forgotten.
  * `scripts/_lf52_wide.py`: handed the engine's true six pads, `plan_moves` stops claiming a win
    (`solved` False, which is the right answer) AND TAKES THE IDENTICAL FATAL MOVE, because tier 1
    is "cheapest route to one more capture" and that capture is the cheapest.

So widening perception fixes the CLAIM and not the MOVE. This probe asks the only question left
before anything is built: on the wide map, does a SURVIVABILITY rule — railpeg's, the one measured
inert on the two-cell window — separate the fatal capture from a safe one?

Every distinct capture OUTCOME reachable within a cost cap is enumerated (keyed by the pieces, not
by the path: one action drives every cart, so hundreds of drive orders reach the same board), and
each is scored two ways that must not be confused:

  pegjump says   `capture_reachable` — is ANOTHER capture still cheaply reachable afterwards? This
                 is all the tool can compute, and it is a proxy.
  the ENGINE says `winnable` — is a two-pad position still reachable? This is the truth, and it
                 comes from `scripts/_lf52_l6_model.py` searched exhaustively.

CONTROLS (rule 7ai)
  POSITIVE  the root must be winnable and uncapped, and the fatal candidate must be present in the
            enumeration with `winnable` False. An enumeration that cannot find the known-bad move
            has measured nothing.
  NEGATIVE  at least one enumerated candidate must be `winnable` True, or the position is lost
            before this decision and the whole question is misplaced.

Expected feedback:
  a candidate with `reachable` True and `winnable` True exists while the fatal one has `reachable`
            False -> the survivability rule SEPARATES them on a wide map; perception + railpeg's
            existing rule is the repair, and both halves are needed.
  the fatal candidate also has `reachable` True         -> the proxy does not separate them; no
            rule available to the tool avoids this move, and lf52's remaining distance is not here.
"""
from __future__ import annotations

import heapq
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_M = importlib.util.spec_from_file_location(
    "lf52_l6_model", Path(__file__).resolve().parent / "_lf52_l6_model.py")
L6 = importlib.util.module_from_spec(_M)
_M.loader.exec_module(L6)

_W = importlib.util.spec_from_file_location(
    "lf52_wide", Path(__file__).resolve().parent / "_lf52_wide.py")
WIDE = importlib.util.module_from_spec(_W)
_W.loader.exec_module(WIDE)

COST_CAP = 26
NODE_CAP = 200_000
REACH_CAP = 25_000


def capture_reachable(pj, state, sockets, rails, noncapture, node_cap=REACH_CAP) -> bool:
    """Can ANOTHER capture still be reached from here? Bounded — False means "not cheaply"."""
    total = len(state[0])
    cost_of = {state: 0}
    heap = [(0, 0, state)]
    tie = 0
    while heap:
        cost, _t, st = heapq.heappop(heap)
        if cost > cost_of.get(st, cost):
            continue
        if len(st[0]) < total:
            return True
        if len(cost_of) > node_cap:
            return False
        for ns, _mv, step in pj._successors(st, sockets, rails, noncapture):
            nc = cost + step
            if nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    return False


def candidates(pj, m, noncapture):
    """Every distinct capture OUTCOME within the cost cap, cheapest first, with its path."""
    start = (tuple(sorted(m.pieces.items())), tuple(sorted(m.carriers)),
             tuple(sorted(m.blockers)))
    total = len(m.pieces)
    cost_of = {start: 0}
    parent: dict = {}
    heap = [(0, 0, start)]
    tie = 0
    seen_outcomes: set = set()
    out = []
    while heap:
        cost, _t, st = heapq.heappop(heap)
        if cost > cost_of.get(st, cost) or cost > COST_CAP:
            continue
        if len(st[0]) < total and st[0] not in seen_outcomes:
            seen_outcomes.add(st[0])
            path = []
            node = st
            while node in parent:
                node, mv = parent[node]
                path.append(mv)
            path.reverse()
            out.append((cost, st, path))
        if len(cost_of) > NODE_CAP:
            break
        for ns, mv, step in pj._successors(st, m.sockets, m.rails, noncapture):
            nc = cost + step
            if nc <= COST_CAP and nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (st, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    return out


def main() -> None:
    from admorphiq.tools import pegjump as pj

    root = (tuple(sorted(WIDE.PADS123.items())), WIDE.CARTS123, WIDE.OX123)
    win, capped, n = WIDE.winnable(root)
    out = {"probe": "lf52_wsurv", "ctrl_root_winnable": win, "ctrl_root_capped": capped,
           "ctrl_root_states": n}

    m = WIDE.build(pj, WIDE.PADS123, WIDE.CARTS123, only_visible=False)
    nc = frozenset()
    cands = candidates(pj, m, nc)
    out["n_candidates"] = len(cands)

    rows = []
    for cost, st, path in cands[:24]:
        first = WIDE._engine_move(path[0]) if path else None
        # The engine's verdict on the WHOLE path, replayed move by move; a path the engine refuses
        # is reported as such rather than scored (the drive model is approximate off the rails).
        state, played = root, 0
        for mv in path:
            nxt = WIDE.apply_engine(state, WIDE._engine_move(mv))
            if nxt is None:
                break
            state, played = nxt, played + 1
        rec = {"cost": cost, "moves": len(path), "first": first,
               "engine_plays": played, "engine_completes": played == len(path),
               "reachable": capture_reachable(pj, st, m.sockets, m.rails, nc)}
        if played == len(path):
            w, cp, ns = WIDE.winnable(state)
            rec["winnable"] = w
            rec["capped"] = cp
            rec["states"] = ns
            rec["pads_after"] = len(state[0])
        rows.append(rec)
    out["candidates"] = rows

    fatal = [r for r in rows if r["first"] and r["first"].get("from") == [14, 2]
             and r["first"].get("to") == [16, 2]]
    out["fatal_present"] = bool(fatal)
    out["fatal"] = fatal[0] if fatal else None
    playable = [r for r in rows if r.get("engine_completes")]
    out["ctrl_pos_ok"] = bool(fatal) and fatal[0].get("winnable") is False
    out["ctrl_neg_ok"] = any(r.get("winnable") is True for r in playable)
    safe = [r for r in playable if r.get("winnable") is True]
    out["n_playable"] = len(playable)
    out["n_safe"] = len(safe)
    out["safe_and_reachable"] = sum(1 for r in safe if r["reachable"])
    out["separates"] = bool(fatal) and (not fatal[0]["reachable"]) and out["safe_and_reachable"] > 0
    print(json.dumps(out))


if __name__ == "__main__":
    main()
