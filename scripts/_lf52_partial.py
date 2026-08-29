"""lf52 level 6 — would "the map is PARTIAL, so a win is not a win" fire, and what would it cost?

⛔ THE THREE MEASUREMENTS THIS FOLLOWS, so none of them is re-asked.
  1. `scripts/_lf52_pcen.py` — the four missing pads are lost to the CAMERA and to nothing else.
     14 socket squares in the frame, exactly 2 discs, `off_phase_discs` 0, `disc_colour_refused` 0,
     `model_pieces_peak` 2 for the whole level. No filter drops a pad and nothing is forgotten.
  2. `scripts/_lf52_wide.py` — handed the engine's true SIX pads, `plan_moves` stops claiming a win
     (`solved` False, correctly) and TAKES THE IDENTICAL FATAL MOVE. Widening perception fixes the
     CLAIM, not the MOVE.
  3. `scripts/_lf52_wsurv.py` — on that wide map the position offers exactly ONE capture outcome
     within cost 26, it is the fatal one, and `capture_reachable` after it is FALSE. The
     survivability rule REFUSES it. So the two halves compose: refuse the local win, and the move
     is re-read as a capture route, where the guard that already exists can see it.

⭐ AND THE WINDOW MAP GIVES THE SAME VERDICT FOR FREE: two pieces, jump one over the other, one
piece left, no pair, so no further capture is reachable either. If the win claim were refused, the
guard would fire WITHOUT any perception change at all. That is the claim this probe tests, live.

railpeg reaches this through `_elsewhere`, which is set by a REFUTED claim — it must play one bad
win first. Here the first claim IS the fatal move, so the signal has to be a-priori. Two candidates,
both computable from what `pegjump` already holds, and both recorded at every decision:

  OFFSCREEN  railpeg's `_offscreen` shape — a socket or rail cell whose track continues off the
             window into cells the map has never held. "The board runs off the screen here."
  EDGE       the weaker form: any known cell on the boundary of the window at all.

CONTROLS (rule 7ai)
  NEGATIVE   per-level actions [8, 52, 60, 64, 139] and total 823 — this probe reads and never
             steers (rule 7aj.2).
  POSITIVE   `decisions_l6` > 0 and the fatal decision is among them, identified by the plan it
             returns, not by its index.

Expected feedback:
  `offscreen` True at the fatal decision, and the counterfactual refusing the win then refusing the
             capture -> the composed rule fires with NO perception change, and it is buildable.
  `offscreen` False there -> the a-priori signal is absent and the repair needs the refuted-claim
             route, which cannot help a tool whose first claim is the losing move.
  `would_refuse_capture` False -> the guard still cannot see it and the whole line is closed.
"""
from __future__ import annotations

import heapq
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823
REACH_CAP = 25_000

_F = importlib.util.spec_from_file_location(
    "lf52_fate", Path(__file__).resolve().parent / "_lf52_fate.py")
FATE = importlib.util.module_from_spec(_F)
_F.loader.exec_module(FATE)


def _offscreen(m, track, cell, d) -> bool:
    """railpeg's shape: the track continues off the window into cells never held."""
    n = (cell[0] + d[0], cell[1] + d[1])
    back = (cell[0] - d[0], cell[1] - d[1])
    known = m.sockets | m.rails | m.blockers | m.carriers
    return back in track and n not in known and n not in m.window


def _partial(pj, m) -> dict:
    track = m.rails | m.carriers
    off = any(_offscreen(m, track, c, d) for c in (m.sockets | track) for d in pj.DIRS)
    known = m.sockets | m.rails | m.blockers | m.carriers
    if m.window:
        rows = [c[0] for c in m.window]
        cols = [c[1] for c in m.window]
        r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
        edge = any(c[0] in (r0, r1) or c[1] in (c0, c1) for c in known)
    else:
        edge = False
    return {"offscreen": bool(off), "edge": bool(edge), "known": len(known),
            "window": len(m.window)}


def _capture_reachable(pj, state, sockets, rails, noncapture, node_cap=REACH_CAP) -> bool:
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


def _counterfactual(pj, m, noncapture) -> dict:
    """What `plan_moves` would do with the win claim REFUSED — the capture route and its verdict.

    Computed read-only beside the real planner; nothing here steers the run.
    """
    if not m.pieces:
        return {"plan": None}
    counts = Counter(m.pieces.values())
    targets = {c for c, n in counts.items() if n >= 2 and c not in noncapture}
    if not targets:
        return {"plan": None, "why": "no-pair"}
    total = len(m.pieces)
    start = (tuple(sorted(m.pieces.items())), tuple(sorted(m.carriers)),
             tuple(sorted(m.blockers)))
    cost_of = {start: 0}
    parent: dict = {}
    heap = [(0, 0, start)]
    tie = 0
    seen_outcomes: set = set()
    cands = []
    expanded = 0
    while heap and len(cands) < 8:
        cost, _t, st = heapq.heappop(heap)
        if cost > cost_of.get(st, cost):
            continue
        if len(st[0]) < total and st[0] not in seen_outcomes:
            seen_outcomes.add(st[0])
            path = []
            node = st
            while node in parent:
                node, mv = parent[node]
                path.append(mv)
            path.reverse()
            cands.append((cost, st, path))
        expanded += 1
        if expanded > pj._NODE_CAP:
            break
        for ns, mv, step in pj._successors(st, m.sockets, m.rails, noncapture):
            nc = cost + step
            if nc < cost_of.get(ns, 1 << 30):
                cost_of[ns] = nc
                parent[ns] = (st, mv)
                tie += 1
                heapq.heappush(heap, (nc, tie, ns))
    if not cands:
        return {"plan": None, "why": "no-capture"}
    verdicts = [bool(_capture_reachable(pj, st, m.sockets, m.rails, noncapture))
                for _c, st, _p in cands]
    first = cands[0][2][0] if cands[0][2] else None
    return {"plan": "capture", "n_candidates": len(cands),
            "survivable": sum(verdicts), "all_fatal": not any(verdicts),
            "first_move": None if first is None else [first[0], list(first[1] or []),
                                                      list(first[2])],
            "first_len": len(cands[0][2])}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import pegjump as pj

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

    view: dict = {"dec": None}
    raw_plan = pj.PegJumpTool._ensure_plan

    def wrapped_plan(self, m):
        had = bool(self._plan)
        score = raw_plan(self, m)
        if had:
            return score
        found = pj.plan_moves(m, self._noncapture)
        rec = _partial(pj, m)
        rec["pieces"] = len(m.pieces)
        rec["carriers"] = len(m.carriers)
        rec["score"] = score
        if found is None or not found[0]:
            rec["tier"] = "explore-or-none"
        else:
            moves, solved = found
            rec["tier"] = "win" if solved else "capture"
            mv = moves[0]
            rec["first_move"] = [mv[0], list(mv[1] or []), list(mv[2])]
            rec["cf"] = _counterfactual(pj, m, self._noncapture) if solved else None
            if not solved:
                st = (tuple(sorted(m.pieces.items())), tuple(sorted(m.carriers)),
                      tuple(sorted(m.blockers)))
                for mv2 in moves:
                    st = pj.PegJumpTool._apply(m, st, mv2)
                rec["capture_reachable_after"] = bool(
                    _capture_reachable(pj, st, m.sockets, m.rails, self._noncapture))
        view["dec"] = rec
        return score

    pj.PegJumpTool._ensure_plan = wrapped_plan

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    held: dict = {}
    real_make = arcade.make

    def make(gid, *a, **k):
        env = real_make(gid, *a, **k)
        held["env"] = env
        return env

    arcade.make = make
    rows: list[dict] = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                o = FATE._oracle(held.get("env"))
                loop = FATE._loop_of(inner)
                view["dec"] = None
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["tool"] = None if loop is None else loop._current
                    o["dec"] = view["dec"]
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "probe": "lf52_partial",
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
    }
    six = [r for r in rows if r["lvl"] == 6]
    decs = [{"i": i, "pads": len(six[i]["pads"]), **six[i]["dec"]}
            for i in range(len(six)) if six[i]["dec"] is not None]
    out["decisions_l6"] = len(decs)
    out["control_pos_ok"] = len(decs) > 0
    out["tiers"] = dict(Counter(d["tier"] for d in decs))
    out["offscreen_true"] = sum(1 for d in decs if d["offscreen"])
    out["edge_true"] = sum(1 for d in decs if d["edge"])
    fatal = [d for d in decs if d.get("first_move")
             and d["first_move"][0] == "jump" and d["tier"] == "win"]
    out["win_claims"] = len(fatal)
    out["fatal_decision"] = next((d for d in decs if d["i"] == 122), None)
    out["decisions"] = decs[:40]
    # The composed rule's verdict wherever a win was claimed.
    cfs = [d["cf"] for d in decs if d["tier"] == "win" and d.get("cf")]
    out["cf_all_fatal"] = sum(1 for c in cfs if c.get("all_fatal"))
    out["cf_capture_plans"] = sum(1 for c in cfs if c.get("plan") == "capture")
    out["cf_none"] = sum(1 for c in cfs if c.get("plan") is None)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
