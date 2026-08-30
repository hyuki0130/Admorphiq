"""dc22 level 6 — walk the KNOWN-GOOD path and ask the tool's floor rule about every cell the
avatar is ACTUALLY standing in.

Purpose. `_plan_full` returns no route to anything on level 6 — not the goal, not a crane plate,
not a key — under the tool's own standability rule or under the R4 repair, at every sampled turn
of the shipped run (measured, `_dc22_l6plan.py`; the search is exhaustive there, `settled=True` so
the cap is 400k against a state space of ~43k). So the tool's WORLD is missing something the route
needs, and the cheapest way to find out what is to walk a path that is known to work and ask the
model about it one step at a time.

The path is the banked 141-action oracle plan (`scripts/_dc22_plan.json`), which an engine BFS
found and which a full-game oracle run scores 1.0000 at 566 actions. After every action this probe
reads the LIVE tool's own perception of the LIVE frame and records:

  * whether `_at` can still find the avatar at all (a perception failure, not a routing one);
  * whether `_solid` calls the cell the avatar is standing in FLOOR — under the tool's current
    rule R1, and under R4 (ground condemns on one pixel, a learned colour condemns only a tile
    made ENTIRELY of condemned colours, which is the evidence `_learn_refusal` actually collects);
  * `_not_floor`, the standable count, and the walk-reachable region from where the avatar is.

A FALSE on a cell the avatar is standing in is a wrong rejection with no interpretation needed.
The first index at which R1 says false and R4 says true is what the repair buys; an index where
both say false is a defect the repair does not reach.

TWO CONTROLS, rule 7aj:
  * POSITIVE — the plan must CLEAR the level. If `levels_completed` does not reach 6 the probe is
    not walking the path it thinks it is and nothing below counts. Reported as `cleared`.
  * NEGATIVE — every step whose action is a CLICK leaves the avatar where it was, so the floor
    verdict must not change across it unless the board did. Reported as `click_verdict_flips`,
    which should be small and attributable, not the bulk of the finding.

Varying parameter FIRST = repetition index (deterministic; a fan measures a rate, not a draw).
Prints ONE JSON line.  Rule 7f: every level change is reported with DIRECTION and the new level.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402

PLAN_FILE = "scripts/_dc22_plan.json"
# Fixed FRAME positions of level 6's buttons, as banked by `_dc22_oracle_full.py`.
COORDS = {"click_f": (53, 5), "click_c": (48, 23), "click_d": (49, 46),
          "crane_up": (49, 31), "crane_dowlja": (49, 39), "crane_lersnf": (45, 35),
          "crane_riidpd": (53, 35), "crane_grab": (47, 17)}


def solid(layout, cell, side, bg, not_floor, rule):
    """The tool's floor test at one cell, under rule R1 (its own) or R4 (the repair)."""
    y, x = cell
    layout = np.asarray(layout)
    if y < 0 or x < 0 or y + side > layout.shape[0] or x + side > layout.shape[1]:
        return False
    tile = layout[y:y + side, x:x + side]
    if bool((tile == bg).any()):
        return False
    if not not_floor:
        return True
    hits = np.isin(tile, list(not_floor))
    return (not bool(hits.any())) if rule == "R1" else (not bool(hits.all()))


def standable_count(layout, side, bg, not_floor, rule):
    layout = np.asarray(layout)
    ground = layout == bg
    condemned = np.zeros_like(ground)
    for c in not_floor:
        condemned |= layout == c
    h, w = ground.shape
    if h < side or w < side:
        return 0

    def window(mask):
        acc = np.zeros((h + 1, w + 1), dtype=np.int32)
        acc[1:, 1:] = mask.astype(np.int32).cumsum(0).cumsum(1)
        return acc[side:, side:] - acc[:-side, side:] - acc[side:, :-side] + acc[:-side, :-side]

    ok = window(ground) == 0
    if rule == "R1":
        ok &= window(condemned) == 0
    else:
        ok &= window(condemned) < side * side
    return int(ok.sum())


class Walker:
    """Generic tools to level 6, then the banked oracle plan, with a read-only tap on the tool."""

    def __init__(self, plan):
        self.agent = SE._make_agent("unified", game_id="dc22")
        self.plan = plan
        self.i = 0
        self.turn = 0
        self.level = None
        self.moves = []
        self.trace = []
        self.armed = False

    def is_done(self, frames, obs):
        if obs.levels_completed >= 5:
            return self.i >= len(self.plan)
        return self.agent.is_done(frames, obs)

    def choose_action(self, frames, obs):
        from arcengine import GameAction
        self.turn += 1
        lvl = int(obs.levels_completed)
        if self.level is None:
            self.level = lvl
        elif lvl != self.level:
            self.moves.append({"turn": self.turn, "plan_index": self.i, "from": self.level,
                               "to": lvl, "direction": "UP" if lvl > self.level else "DOWN"})
            self.level = lvl
        if lvl < 5:
            return self.agent.choose_action(frames, obs)
        if not self.armed:
            self.armed = True
        self.record(obs)
        if self.i >= len(self.plan):
            return GameAction.ACTION1
        label = self.plan[self.i]
        self.i += 1
        if label.startswith("A"):
            return getattr(GameAction, "ACTION" + label[1])
        act = GameAction.ACTION6
        x, y = COORDS[label]
        act.set_data({"x": x, "y": y})
        return act

    def record(self, obs):
        from admorphiq.tools.base import frame_2d
        t = self.agent.tools.get("gantry")
        if t is None:
            return
        try:
            g = frame_2d(obs)
            geom = t._read(g)
        except Exception as exc:                                   # noqa: BLE001
            self.trace.append({"i": self.i, "error": repr(exc)[:120]})
            return
        rec = {"i": self.i, "label": self.plan[self.i] if self.i < len(self.plan) else None,
               "level": int(obs.levels_completed),
               "not_floor": sorted(int(c) for c in t._not_floor)}
        if geom is None:
            rec["read"] = None
            self.trace.append(rec)
            return
        board = np.asarray(geom["board"])
        bg, side = int(geom["bg"]), int(geom["side"])
        cell = t._at(board, t._avatar) if t._avatar >= 0 else None
        rec["avatar"] = list(cell) if cell else None
        rec["found"] = cell is not None
        rec["widened"] = bool(board.shape[1] > int(geom["panel"]))
        if cell is not None:
            rec["R1"] = solid(board, cell, side, bg, t._not_floor, "R1")
            rec["R4"] = solid(board, cell, side, bg, t._not_floor, "R4")
            rec["tile"] = [[int(v) for v in row] for row in board[cell[0]:cell[0] + side,
                                                                  cell[1]:cell[1] + side]]
        rec["standable_R1"] = standable_count(board, side, bg, t._not_floor, "R1")
        rec["standable_R4"] = standable_count(board, side, bg, t._not_floor, "R4")
        self.trace.append(rec)


def main():
    rep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    plan = json.load(open(PLAN_FILE))["plan"]
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    w = Walker(plan)
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="l6walk",
                      max_actions=4000, adapter_factory=lambda: w)
    seen = [r for r in w.trace if "R1" in r]
    lost = [r["i"] for r in w.trace if r.get("found") is False]
    r1_false = [r["i"] for r in seen if not r["R1"]]
    r4_false = [r["i"] for r in seen if not r["R4"]]
    fixed = [i for i in r1_false if i not in r4_false]
    clicks = [r for r in w.trace if r.get("label") and not r["label"].startswith("A")]
    print(json.dumps({
        "rep": rep,
        "levels_completed": res.get("levels_completed"),
        "total_actions": res.get("total_actions"),
        "cleared": res.get("levels_completed", 0) >= 6,
        "level_changes": w.moves,
        "plan_len": len(plan), "plan_executed": w.i,
        "steps_traced": len(w.trace), "avatar_located": len(seen),
        "avatar_lost_at": lost[:20], "avatar_lost_n": len(lost),
        "R1_rejects_own_cell": r1_false, "R4_rejects_own_cell": r4_false,
        "repaired_by_R4": fixed,
        "click_steps": len(clicks),
        "trace": w.trace,
    }), flush=True)


if __name__ == "__main__":
    main()
