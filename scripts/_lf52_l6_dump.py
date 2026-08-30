"""What is WRONG with railpeg's map at the exact action it lets lf52 level 6 go — and is that it?

Measured first (scripts/_lf52_l6_hold.py, both seeds identical): at level-6 action 114 the tool
bids 0.0 for eight decisions running with `known` 98, `pieces` 5, `aboard` 0, every tier reporting
no gain — and the position it hands on is WINNABLE in 242,384 states. Measured second
(scripts/_lf52_l6_plan.py): handed the WHOLE board, railpeg's own `_ensure_plan` loop takes level 6
down to one green in 57 decisions. So the planner is sufficient and the map is not.

This names the difference and then tests whether the difference is the CAUSE:

  1. dump the model at the first zero bid, align it to the level data, and report what is missing
     and what is invented;
  2. re-run the tool's own decision loop from that model UNCHANGED  -> reproduces the stall;
  3. re-run it from the same model with the MISSING PIECES restored -> does the level fall out?
  4. re-run it from the same model with the invented cells struck   -> or is it the phantoms?

CONTROLS (rule 7aj.3), printed before any verdict:
  NEGATIVE  per-level [8, 52, 60, 64, 139] / 823, and arm 2 must NOT win. An arm set in which
            everything wins is measuring the harness, not the map.
  POSITIVE  the full-board arm must win — the same claim scripts/_lf52_l6_plan.py makes, re-made
            here so a change to the tool cannot silently invalidate this probe.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823

_P = importlib.util.spec_from_file_location(
    "lf52_l6_plan", Path(__file__).resolve().parent / "_lf52_l6_plan.py")
PL = importlib.util.module_from_spec(_P)
_P.loader.exec_module(PL)


def _scene(env):
    g = getattr(env, "_game", None) or getattr(env, "game", None)
    return getattr(g, "ikhhdzfmarl", None) if g is not None else None


def _oracle(env):
    sc = _scene(env)
    grid = getattr(sc, "hncnfaqaddg", None) if sc is not None else None
    if grid is None:
        return None
    return {"lvl": int(getattr(sc, "whtqurkphir", -1)),
            "cam": list(getattr(grid, "cdpcbbnfdp", (0, 0))),
            "pads": sorted((tuple(p.chahdtpdoz), str(p.name))
                           for p in grid.ndtvadsrqf("fozwvlovdui"))}


def _snapshot(m):
    return {"sockets": sorted(m.sockets), "rails": sorted(m.rails),
            "obstacles": sorted(m.obstacles), "carts": sorted(m.carts),
            "cargo": sorted(m.cargo), "pieces": sorted(m.pieces.items()),
            "window": sorted(m.window)}


def _restore(snap):
    from admorphiq.tools.railpeg import Model
    m = Model()
    m.pitch = 6
    m.sockets = {tuple(c) for c in snap["sockets"]}
    m.rails = {tuple(c) for c in snap["rails"]}
    m.obstacles = {tuple(c) for c in snap["obstacles"]}
    m.carts = {tuple(c) for c in snap["carts"]}
    m.cargo = {tuple(c) for c in snap["cargo"]}
    m.pieces = {tuple(c): v for c, v in snap["pieces"]}
    m.window = {tuple(c) for c in snap["window"]}
    return m


def _best_offset(model_known, truth_known):
    best = None
    for a in sorted(model_known)[:20]:
        for b in truth_known:
            off = (b[0] - a[0], b[1] - a[1])
            hits = len({(c[0] + off[0], c[1] + off[1]) for c in model_known} & truth_known)
            if best is None or hits > best[0]:
                best = (hits, off)
    return best


def _run_loop(m, noncapture, limit=400):
    """railpeg's own decision loop over a model, with no engine — returns (won, steps, why)."""
    from admorphiq.tools.railpeg import RailPegTool, _ground, _successors
    tool = RailPegTool()
    tool.reset()
    tool._noncapture = noncapture
    tool._model = m
    tool._touched = set(m.pieces)
    tool._ntouched = len(tool._touched)
    tool._peaked = max(2, len(m.pieces))
    tool._elsewhere = True
    steps = 0
    for _ in range(limit):
        if sum(1 for v in m.pieces.values() if v == PL.GREEN) <= 1:
            return True, steps, dict(Counter(tool._why).most_common(8)), dict(tool._tiers)
        if not tool._plan and not tool._ensure_plan(m):
            break
        if not tool._plan:
            break
        mv = tool._plan.pop(0)
        if not any(x == mv for _ns, x, _c in _successors(m.state(), _ground(m), noncapture)):
            tool._plan = []
            continue
        tool._advance(m, mv)
        steps += 1
    return False, steps, dict(Counter(tool._why).most_common(8)), dict(tool._tiers)


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.railpeg import RailPegTool

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

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

    at6 = [False]
    grab: dict = {}
    fired = [0]
    raw_ensure = RailPegTool._ensure_plan

    def ensure(self, m):
        bid = raw_ensure(self, m)
        if at6[0]:
            fired[0] += 1
            if not bid and "snap" not in grab:
                grab["snap"] = _snapshot(m)
                grab["noncapture"] = sorted(self._noncapture)
                grab["truth"] = _oracle(held.get("env"))
        return bid

    RailPegTool._ensure_plan = ensure
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                o = _oracle(held.get("env"))
                at6[0] = bool(o is not None and o["lvl"] == 6)
                return inner.choose_action(frames, obs)

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {"probe": "lf52_l6_dump", "per_level": per,
                 "total_actions": int(res.get("total_actions", -1)),
                 "ctrl_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
                 "ctrl_fired": fired[0]}
    if "snap" not in grab:
        out["error"] = "railpeg never bid zero on level 6"
        print(json.dumps(out))
        return

    RailPegTool._ensure_plan = raw_ensure
    snap = grab["snap"]
    nc = frozenset(grab["noncapture"])
    out["noncapture"] = sorted(nc)
    truth = PL.build()
    tk = truth.known() | truth.carts
    mk = {tuple(c) for c in snap["sockets"]} | {tuple(c) for c in snap["rails"]} \
        | {tuple(c) for c in snap["obstacles"]} | {tuple(c) for c in snap["carts"]}
    hits, off = _best_offset(mk, tk)
    out["align"] = {"hits": hits, "off": list(off), "model_cells": len(mk), "true_cells": len(tk)}

    def shift(c):
        return (c[0] + off[0], c[1] + off[1])

    shifted = {shift(tuple(c)) for c in mk}
    out["missing_cells"] = sorted(tk - shifted)
    out["phantom_cells"] = sorted(shifted - tk)
    mp = {shift(tuple(c)): v for c, v in snap["pieces"]}
    out["model_pieces"] = sorted(mp.items())
    out["true_pieces"] = sorted(truth.pieces.items())
    out["missing_pieces"] = sorted(set(truth.pieces) - set(mp))
    out["phantom_pieces"] = sorted(set(mp) - set(truth.pieces))
    out["engine_pads"] = grab["truth"]["pads"] if grab["truth"] else None
    out["cam"] = grab["truth"]["cam"] if grab["truth"] else None

    # ARM 2 — the model exactly as the tool held it. Must NOT win (negative control).
    won2, st2, why2, ti2 = _run_loop(_restore(snap), nc)
    out["arm_asis"] = {"won": won2, "steps": st2, "why": why2, "tiers": ti2}

    # ARM 3 — same map, missing pieces restored in the tool's own coordinates.
    s3 = json.loads(json.dumps(snap))
    inv = (-off[0], -off[1])
    for cell in out["missing_pieces"]:
        c = (cell[0] + inv[0], cell[1] + inv[1])
        s3["pieces"].append([list(c), truth.pieces[tuple(cell)]])
        if list(c) not in s3["sockets"]:
            s3["sockets"].append(list(c))
    won3, st3, why3, ti3 = _run_loop(_restore(s3), nc)
    out["arm_pieces_restored"] = {"won": won3, "steps": st3, "why": why3, "tiers": ti3}

    # ARM 4 — same pieces as the tool had, but the map's invented cells struck out.
    s4 = json.loads(json.dumps(snap))
    bad = {(c[0] + inv[0], c[1] + inv[1]) for c in out["phantom_cells"]}
    for k in ("sockets", "rails", "obstacles", "carts"):
        s4[k] = [c for c in s4[k] if tuple(c) not in bad]
    won4, st4, why4, ti4 = _run_loop(_restore(s4), nc)
    out["arm_phantoms_struck"] = {"won": won4, "steps": st4, "why": why4, "tiers": ti4}

    # ARM 5 — both corrections at once.
    s5 = json.loads(json.dumps(s3))
    for k in ("sockets", "rails", "obstacles", "carts"):
        s5[k] = [c for c in s5[k] if tuple(c) not in bad]
    won5, st5, why5, ti5 = _run_loop(_restore(s5), nc)
    out["arm_both"] = {"won": won5, "steps": st5, "why": why5, "tiers": ti5}

    # POSITIVE control — the whole board, re-made here.
    wonF, stF, _wF, tiF = _run_loop(PL.build(), nc)
    out["ctrl_full_board_wins"] = wonF
    out["ctrl_full_board_steps"] = stF
    out["ctrl_full_board_tiers"] = tiF
    print(json.dumps(out))


if __name__ == "__main__":
    main()
