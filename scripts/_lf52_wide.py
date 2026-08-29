"""lf52 level 6 — if `pegjump` SAW THE WHOLE BOARD, would it still make the losing move?

⛔ TEST THE REPAIR BEFORE BUILDING IT (the briefing's own instruction). `scripts/_lf52_pcen.py`
measured that the pads are lost to the CAMERA and to nothing else: at level-6 action 122 the frame
carries 14 socket squares and exactly 2 discs, `off_phase_discs` 0 and `disc_colour_refused` 0, so
no filter drops anything — and `model_pieces_peak` is 2 for the whole level, so the model never held
more and never forgot any. The pads at (6,6), (22,5) and (26,3) are simply not on the screen.

That leaves the question the briefing asks third, and it is the one that decides whether widening
perception is worth building at all: **give the planner the engine's true six pads and ask what it
does.** No engine, no frame, no run — the truth is `scripts/_lf52_l6_model.py`'s own board and the
position is the one `scripts/_lf52_fate.py` recorded at the losing move.

Three models are planned from, so the answer is attributable:
  WINDOW  exactly what the tool had: the two pads and two carts inside the screen. This must
          reproduce the observed defect — `solved` True on a jump of one piece over the other —
          or the reconstruction is wrong and nothing below means anything.
  WIDE    the engine's true six pads, three carts, whole map.
  WIDE-NC the same with the red pad's colour marked uncapturable, which is what the tool would
          learn after one refused capture.

⛔ AND THE VERDICT IS TAKEN FROM THE ENGINE'S OWN SOLVER, not from the plan looking sensible: the
state each plan's FIRST move leads to is rebuilt as an `_lf52_l6_model` state and searched for a
two-pad position, exactly as `_lf52_fate.py` does.

CONTROLS (rule 7ai)
  POSITIVE  the WIDE root must be WINNABLE and uncapped — a solver that cannot say YES about a
            position the fate probe already called winnable has measured nothing.
  NEGATIVE  the WINDOW arm must return `solved` True with the jump (14,2)->(16,2), the move the
            live run made. Anything else means this is not the tool's position.

Expected feedback:
  WIDE's first move is NOT the fatal capture, and is winnable -> perception is the whole repair;
            widening the map is worth building.
  WIDE's first move is the fatal capture too                   -> widening perception does NOT fix
            this move, and the repair is survivability inside the planner, on a wider map.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_M = importlib.util.spec_from_file_location(
    "lf52_l6_model", Path(__file__).resolve().parent / "_lf52_l6_model.py")
L6 = importlib.util.module_from_spec(_M)
_M.loader.exec_module(L6)

NODE_CAP = 700_000

# The engine's own state at the action before the losing move (scripts/_lf52_fate.py, banked run).
PADS123 = {(6, 6): "fozwvlovdui_red", (14, 2): "fozwvlovdui", (15, 2): "fozwvlovdui",
           (20, 7): "fozwvlovdui", (22, 5): "fozwvlovdui", (26, 3): "fozwvlovdui"}
CARTS123 = ((11, 6), (14, 4), (25, 2))
OX123 = -57

GREEN, RED = 0, 1


def _key(s):
    return (tuple((c, 1 if "red" in n else 0) for c, n in s[0]), s[1], s[2])


def winnable(state) -> tuple[bool, bool, int]:
    seen = {_key(state)}
    q = deque([state])
    n = 0
    while q:
        s = q.popleft()
        if len(s[0]) == 2:
            return True, False, n
        n += 1
        if n > NODE_CAP:
            return False, True, n
        for ns, _mv in L6.successors(s):
            k = _key(ns)
            if k not in seen:
                seen.add(k)
                q.append(ns)
    return False, False, n


def _visible(cell, ox=OX123) -> bool:
    return L6.onscreen(cell, ox)


def build(pj, pads, carts, only_visible: bool):
    """A `pegjump` Model over the engine's truth. Cells are transposed: pegjump is (row, col)."""
    m = pj.Model()
    m.pitch, m.oy, m.ox = L6.CELL, 5, OX123
    for cell, names in L6.STATIC.items():
        if only_visible and not _visible(cell):
            continue
        rc = (cell[1], cell[0])
        # A landing is bare floor or a cart; a stone's cell is not landable, so it is furniture.
        if names == ["hupkpseyuim"]:
            m.sockets.add(rc)
        if any("kraubslpehi" in n for n in names):
            m.rails.add(rc)
        if any("dgxfozncuiz" in n for n in names):
            m.blockers.add(rc)
    for c in carts:
        if only_visible and not _visible(c):
            continue
        rc = (c[1], c[0])
        m.carriers.add(rc)
        m.rails.add(rc)
        m.sockets.discard(rc)
    for cell, nm in pads.items():
        if only_visible and not _visible(cell):
            continue
        m.pieces[(cell[1], cell[0])] = RED if "red" in nm else GREEN
    m.window = {(c[1], c[0]) for c in L6.STATIC if _visible(c)}
    return m


def _engine_move(mv):
    """A pegjump move ("jump", (row, col), (dr, dc)) back in the engine's (x, y) terms."""
    kind, cell, d = mv
    if kind != "jump":
        return {"kind": "drive", "d": [d[1], d[0]]}
    src = (cell[1], cell[0])
    de = (d[1], d[0])
    return {"kind": "jump", "from": list(src), "d": list(de),
            "over": [src[0] + de[0], src[1] + de[1]],
            "to": [src[0] + 2 * de[0], src[1] + 2 * de[1]]}


def apply_engine(state, mv):
    """The engine state a pegjump jump leads to, or None when the engine refuses it."""
    if mv["kind"] != "jump":
        for ns, m2 in L6.successors(state):
            if m2[0] == "drive" and list(m2[1]) == mv["d"]:
                return ns
        return None
    src, d = tuple(mv["from"]), tuple(mv["d"])
    for ns, m2 in L6.successors(state):
        if m2[0] == "jump" and m2[1] == src and m2[2] == d:
            return ns
    return None


def arm(pj, name, pads, carts, only_visible, noncapture):
    m = build(pj, pads, carts, only_visible)
    found = pj.plan_moves(m, frozenset(noncapture))
    out = {"arm": name, "pieces": len(m.pieces), "carriers": len(m.carriers),
           "sockets": len(m.sockets), "rails": len(m.rails), "blockers": len(m.blockers)}
    if found is None or not found[0]:
        out["plan"] = None
        return out
    moves, solved = found
    out["solved"] = bool(solved)
    out["plan_len"] = len(moves)
    out["first"] = _engine_move(moves[0])
    out["plan"] = [_engine_move(x) for x in moves[:8]]
    state = (tuple(sorted(pads.items())), tuple(sorted(carts)), OX123)
    ns = apply_engine(state, out["first"])
    if ns is None:
        out["engine_accepts_first"] = False
        return out
    out["engine_accepts_first"] = True
    win, capped, n = winnable(ns)
    out["after_first_winnable"] = win
    out["after_first_capped"] = capped
    out["after_first_states"] = n
    # And the whole plan, as far as the engine will take it.
    st, played = state, 0
    for mv in out["plan"]:
        nx = apply_engine(st, mv)
        if nx is None:
            break
        st, played = nx, played + 1
    out["engine_plays"] = played
    if played:
        win, capped, _n = winnable(st)
        out["after_plan_winnable"] = win
        out["after_plan_capped"] = capped
        out["pads_after_plan"] = len(st[0])
    return out


def main() -> None:
    from admorphiq.tools import pegjump as pj

    root = (tuple(sorted(PADS123.items())), CARTS123, OX123)
    win, capped, n = winnable(root)
    out = {"probe": "lf52_wide", "ctrl_root_winnable": win, "ctrl_root_capped": capped,
           "ctrl_root_states": n}
    arms = [
        arm(pj, "window", PADS123, CARTS123, True, ()),
        arm(pj, "wide", PADS123, CARTS123, False, ()),
        arm(pj, "wide_nc_red", PADS123, CARTS123, False, (RED,)),
    ]
    out["arms"] = arms
    w = arms[0]
    out["ctrl_window_reproduces"] = bool(
        w.get("solved") and w.get("first", {}).get("from") == [14, 2]
        and w.get("first", {}).get("to") == [16, 2])
    print(json.dumps(out))


if __name__ == "__main__":
    main()
