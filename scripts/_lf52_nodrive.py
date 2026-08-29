#!/usr/bin/env python3
"""lf52 — `pegjump` BOARDS a piece and then never RIDES it. Which tier goes silent?

⛔ THE MEASUREMENT THIS ANSWERS (`scripts/_lf52_offframe.py`, R101LF52OFF). At level 6, with the
patience latch removed so the tool gets 378 decisions instead of 19:

    railpeg  121 actions   camera through 12 distinct positions, 47 changes
    pegjump  378 actions   camera through ONE position, ZERO changes
             a piece is ABOARD A CART on 376 of those 378 decisions

So the engine's own scroll rule (b) — "a cart drive while a piece rides it moves the camera" — is
ARMED for 99.5% of the tenure and the tool never fires it. That is not "no action exists"; it is the
tool declining an action that is available. This asks WHICH of its three planning tiers goes silent,
by counting what each returns and what `propose` actually pops.

Per `_ensure_plan` call: the tier that produced the plan (`plan`/`railhead`/`explore`/`probe`/none),
its length, `_barren`, `_known`, and the model's own carrier/piece/rail census. Per `propose` call:
the move kind popped, and whether the ENGINE's camera changed on the action that followed.

ARMS: `pure` control (must be [8,52,60,64,139] / 823), and `patient` (the levered census — measured
in `_lf52_patience.py` to change no per-level count, so it is a magnifier, not a different run).

Usage:  uv run python scripts/_lf52_nodrive.py <seed 1..6>
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
ARMS = ["pure", "patient", "patient", "plain", "plain", "patient"]


def _cam(env):
    g = getattr(env, "_game", None) or getattr(env, "game", None)
    sc = getattr(g, "ikhhdzfmarl", None) if g is not None else None
    grid = getattr(sc, "hncnfaqaddg", None) if sc is not None else None
    return tuple(getattr(grid, "cdpcbbnfdp", (0, 0))) if grid is not None else None


def main() -> None:
    seed = int(sys.argv[1])
    mode = ARMS[(seed - 1) % len(ARMS)]

    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import pegjump as pj

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

    tiers: Counter = Counter()
    tierlen: Counter = Counter()
    moves: Counter = Counter()
    snaps: list[dict] = []
    cur = {"lvl": -1}

    raw_rail, raw_expl, raw_prob = pj.railhead_moves, pj.explore_moves, pj.probe_moves
    last = {"tier": None}

    def mk(name, fn):
        def inner(*a, **k):
            out = fn(*a, **k)
            if cur["lvl"] == 5:
                tiers[f"{name}:{'HIT' if out else 'EMPTY'}"] += 1
                if out:
                    last["tier"] = name
                    tierlen[f"{name}:{len(out)}"] += 1
            return out
        return inner

    pj.railhead_moves = mk("railhead", raw_rail)
    pj.explore_moves = mk("explore", raw_expl)
    pj.probe_moves = mk("probe", raw_prob)

    raw_plan = pj.PegJumpTool._ensure_plan
    raw_propose = pj.PegJumpTool.propose

    def wrapped_plan(self, m):
        last["tier"] = None
        pre = len(self._plan)
        score = raw_plan(self, m)
        if cur["lvl"] == 5:
            src = "kept" if pre else (last["tier"] or ("solve" if score >= 0.9 else "none"))
            tiers[f"ensure:{src}:{score}"] += 1
            snaps.append({"src": src, "score": score, "barren": self._barren,
                          "known": self._known,
                          "carriers": len(m.carriers), "pieces": len(m.pieces),
                          "rails": len(m.rails), "sockets": len(m.sockets),
                          "dirmap": len(self._dirmap), "plan": len(self._plan)})
        if mode == "patient" and self._barren >= 3:
            self._barren = 2
        return score

    refuse: list[dict] = []

    def wrapped_propose(self, frames, obs):
        before = list(self._plan)
        steps = raw_propose(self, frames, obs)
        if cur["lvl"] == 5:
            popped = before[0][0] if before else "-"
            moves[f"{popped}/{len(steps)}"] += 1
            # ⛔ A `drive` popped that emits NOTHING is the thing to name. Snapshot every input the
            # branch reads, so the exact `return []` is identified rather than inferred.
            if popped == "drive" and not steps and len(refuse) < 12:
                from admorphiq.tools.base import availability as _av
                simple, _six = _av(obs)
                d = before[0][2]
                refuse.append({
                    "want": str(d), "simple": sorted(simple),
                    "dirmap": {str(k): v for k, v in self._dirmap.items()},
                    "excluded": {str(k): sorted(v) for k, v in self._excluded.items()},
                    "taken": sorted(set(self._dirmap.values())
                                    | self._excluded.get(d, set())),
                    "plan_after": len(self._plan),
                    "pending": str(self._pending_drive)[:80],
                    # ⛔ WHICH early `return []` fired, without settrace: each of the four is
                    # separated by a field that only it can be responsible for.
                    "settles": self._settles, "misaligned": self._misaligned,
                    "doubt": self._doubt, "peaked": self._peaked,
                    "board_read": self._read is not None,
                    "sync_res": ("None" if self._sync_res is None
                                 else f"placed={self._sync_res[1]}"),
                })
        return steps

    if mode != "pure":
        pj.PegJumpTool._ensure_plan = wrapped_plan
        pj.PegJumpTool.propose = wrapped_propose

    cams: list = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                cur["lvl"] = int(getattr(obs, "levels_completed", -1))
                if mode == "patient" and getattr(inner, "_current", None) == "pegjump":
                    inner._empty_runs = 0
                act = inner.choose_action(frames, obs)
                if cur["lvl"] == 5:
                    cams.append((getattr(inner, "_current", None) or "H", _cam(held.get("env"))))
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    pjcams = [c for w, c in cams if w == "pegjump"]
    out = {
        "arm": {"mode": mode, "seed": seed},
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "l6_pegjump_actions": len(pjcams),
        "l6_pegjump_distinct_cams": len(set(pjcams)),
        "l6_all_distinct_cams": len({c for _w, c in cams}),
        "tiers": dict(tiers),
        "tierlen": dict(tierlen),
        "moves_popped": dict(moves),
        "snaps_head": snaps[:12],
        "snaps_tail": snaps[-6:],
        "snap_n": len(snaps),
        "drive_refusals": refuse,
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
