"""lf52 level 6: FORCE the red piece off the trap cell, and see whether anything opens.

⛔ WHY THIS AND NOT A TIER. Three measurements this pass refuted the framing rule 7au handed over:
`railpeg` refuses the (16,2) capture at ALL 20 of its candidate turns (`capture_reachable` False for
every candidate, `plan_res=None`), bids 0.0 from action 114 and is retired at 121; the fatal jump is
made by `pegjump`; the restart click at action 266 is made by `graph`. So there is no candidate
ORDER to repair inside railpeg. What is left is the other half of the engine's conjunction — the RED
piece standing on (6, 6) — and `_lf52_arm.py` measured that it is NOT frozen: red can legally vacate
that cell at level-6 actions 24, 25, 26, 27, 28, 79, 80 and 81, forty-three actions before the
capture that loses the branch.

So the question is asked ORACULARLY, by doing, exactly as `_lf52_stall.py` asks its own (rule: the
source says what is POSSIBLE, only a run says what HAPPENS). One arm per opportunity: at the k-th
level-6 action where the engine's own predicate says the piece on (6, 6) may jump, this probe plays
that jump itself (two clicks, the game's own select-then-land protocol) and hands control straight
back to the agent. Nothing else is changed.

ARM (argv[1]): -1 = control, plays nothing; 0..7 = force at the k-th opportunity.

CONTROLS (rule 7ai)
  NEGATIVE  the control arm must reproduce [8, 52, 60, 64, 139] / 823 / 0.272727, and every arm
            must reproduce levels 1-5 unchanged — the injection happens on level 6 only.
  POSITIVE  `forced_at` must be non-null on arms 0..7 and the two clicks must be ACCEPTED: `vacated`
            reports whether the engine's piece really left (6, 6). An arm that reports a forced move
            the board never made has measured nothing — ⚠️ and `_lf52_stall.py`'s own control row
            printed a 0 that was a variable's initial value, so every field here is None until
            written.

Expected feedback:
  any arm with `levels_completed` > 5                     -> the trap cell IS the lever; a tier that
        keeps it clear is worth building.
  every arm 5 levels and `zv_at` still ~124               -> vacating changes nothing downstream and
        the "do not strand a piece" axis is CLOSED, cheaply.
  `vacated` False on every arm                            -> the injection is not landing; the arm
        rows are void and nothing may be concluded from them.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823
TRAP = (6, 6)
PITCH = 6


def _scene(env):
    g = getattr(env, "_game", None) or getattr(env, "game", None)
    return getattr(g, "ikhhdzfmarl", None) if g is not None else None


def _oracle(env) -> dict | None:
    sc = _scene(env)
    if sc is None:
        return None
    grid = getattr(sc, "hncnfaqaddg", None)
    if grid is None:
        return None
    try:
        pieces = grid.ndtvadsrqf("fozwvlovdui")
    except Exception:
        return None
    occ = [p for p in pieces if p.chahdtpdoz == TRAP]
    dirs = []
    for d in DIRS:
        for p in occ:
            try:
                if sc.qikmikecdf(p.chahdtpdoz, d):
                    dirs.append(d)
            except Exception:
                pass
    return {
        "lvl": int(getattr(sc, "whtqurkphir", -1)),
        "used": int(getattr(sc, "asqvqzpfdi", -1)),
        "cam": list(getattr(grid, "cdpcbbnfdp", (0, 0))),
        "occupied": bool(occ),
        "vacate_dirs": dirs,
        "zv": bool(getattr(sc, "zvcnglshzcx", False)),
        "p": len(pieces),
    }


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType
    from admorphiq.types import GameAction as InternalAction

    # ⚠️ `pfan.sh` hands every arm its SEED (1..N), not its arm index, so the mapping is stated
    # here rather than left to whoever launches: seed 1 = the control, seeds 2..9 = opportunities
    # 0..7. A probe that silently read the seed as the arm would run the control eight times.
    arm = (int(sys.argv[1]) - 2) if len(sys.argv) > 1 else -1

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

    def click(cell, cam):
        """Screen pixel of a lattice cell, from the engine's own camera offset."""
        return (cell[0] * PITCH + cam[0] + 3, cell[1] * PITCH + cam[1] + 3)

    st = {"opps": 0, "queue": [], "forced_at": None, "forced_dir": None,
          "l6": 0, "post": [], "zv_at": None, "clicks": []}
    rows: list[dict] = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                o = _oracle(held.get("env"))
                if o is not None and o["lvl"] == 6:
                    if o["zv"] and st["zv_at"] is None:
                        st["zv_at"] = st["l6"]
                    # ⛔ Whether the forced jump LANDED is read over the frames after it, never off
                    # the first one: the piece is in flight for several frames and a single reading
                    # taken too early reports the cell still occupied on a jump that worked.
                    if st["forced_at"] is not None and not st["queue"] and len(st["post"]) < 10:
                        st["post"].append(bool(o["occupied"]))
                    if st["queue"]:
                        cell = st["queue"].pop(0)
                        st["l6"] += 1
                        xy = click(cell, o["cam"])
                        st["clicks"].append(list(xy))
                        return AdmorphiqAdapter._convert_action(
                            InternalAction(ActionType.ACTION6, x=int(xy[0]), y=int(xy[1])))
                    if o["occupied"] and o["vacate_dirs"]:
                        k = st["opps"]
                        st["opps"] += 1
                        if k == arm:
                            d = ((1, 0) if (1, 0) in o["vacate_dirs"] else o["vacate_dirs"][0])
                            land = (TRAP[0] + 2 * d[0], TRAP[1] + 2 * d[1])
                            st["forced_at"] = st["l6"]
                            st["forced_dir"] = list(d)
                            st["queue"] = [land]
                            st["l6"] += 1
                            xy = click(TRAP, o["cam"])
                            st["clicks"].append(list(xy))
                            return AdmorphiqAdapter._convert_action(
                                InternalAction(ActionType.ACTION6, x=int(xy[0]), y=int(xy[1])))
                    st["l6"] += 1
                act = inner.choose_action(frames, obs)
                if o is not None:
                    rows.append({"lvl": o["lvl"], "used": o["used"], "p": o["p"], "zv": o["zv"]})
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    six = [r for r in rows if r["lvl"] == 6]
    caps = [i for i in range(1, len(six)) if six[i]["p"] < six[i - 1]["p"]]
    print(json.dumps({
        "probe": "lf52_disarm",
        "arm": arm,
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_neg_ok": (arm != -1) or (per == BANKED
                                          and int(res.get("total_actions", -1)) == BANKED_TOTAL),
        "levels_1_5_unchanged": per[:5] == BANKED,
        "opportunities_seen": st["opps"],
        "forced_at": st["forced_at"],
        "forced_dir": st["forced_dir"],
        "clicks": st["clicks"],
        "post_occupied": st["post"],
        "vacated": (None if not st["post"] else (False in st["post"])),
        "zv_at": st["zv_at"],
        # ⛔ Distinguishes "disarming buys progress that is not enough" from "buys nothing at all".
        "l6_captures": caps,
        "l6_pieces_end": six[-1]["p"] if six else None,
        "l6_pieces_min": min((r["p"] for r in six), default=None),
    }), flush=True)


if __name__ == "__main__":
    main()
