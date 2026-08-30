"""dc22 level 6 — ask the LIVE tool's OWN planner, under its own rule and under the repair.

Purpose. Reachability computed over a FROZEN board understates what `gantry` can do: its search
is over (cell, phase vector, rail position), so a cell that no walk reaches may still be reachable
once a terrain control is pressed. The only honest question is therefore the one the tool itself
asks — `_plan_full` — and this probe asks it, on the live tool, on the shipped run, without
changing a single action.

At sampled turns on level 6 it calls `_plan_full` toward each of: the level's real goal (the
tool's own marker cell), the four crane plates, and the two `piyqze` keys — first under the tool's
CURRENT standability rule, then again with `_standable` swapped for R4, which keeps the board's
ground condemning a tile on one pixel and lets a LEARNED colour condemn only a tile made ENTIRELY
of condemned colours. R4 is not a loosening for its own sake: `_learn_refusal` only ever condemns
a colour from a tile of ONE FLAT COLOUR, so R1 applies a rule strictly stronger than the evidence
that produced it, and R4 makes the two match.

⛔ The swap is READ-ONLY with respect to the run: the plan lengths are computed and thrown away,
the tool's own `_steps` are never touched, and the actions the agent takes are the shipped ones.
The run must still reproduce the banked 925 actions / 5 levels, and reports whether it did.

TWO CONTROLS, rule 7aj:
  * POSITIVE — the level's goal is REACHABLE in the engine (a 141-action oracle plan exists and a
    full-game oracle scores 1.0000), so a planner that returns no plan to it is the thing being
    measured, not a property of the level. And when `_not_floor` is empty the two rules are the
    same rule and every pair of plan lengths must be EQUAL; the probe counts violations.
  * NEGATIVE — a plan to the cell the avatar is ALREADY standing on must be length 0 under both
    rules. A planner that cannot find that is broken and nothing else it says counts.

Varying parameter FIRST = repetition index.  Second = sample stride in level-6 turns.
Prints ONE JSON line.  Rule 7f: any level change is reported with DIRECTION and the new level.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402

# Read from the game's own source (`sprite_81*` tagged `njvd-rolo`, and the two `piyqze` keys) as
# LEVEL coordinates (y, x). Used ONLY to look tiles up in the measured board — nothing here is fed
# to any tool, and each tile's pixels are printed so the lookup can be checked rather than trusted.
L6_CELLS = {"plate_e_left": (58, 32), "plate_b_up": (56, 34), "plate_a_right": (58, 36),
            "plate_h_down": (60, 34), "key_g_grab": (48, 34), "key_d_cycle": (18, 6),
            "goal_goknoi": (6, 46)}


def standable(layout, side, bg, not_floor, rule):
    """Avatar-sized tiles that count as floor, under one of three rules."""
    layout = np.asarray(layout)
    ground = layout == bg
    condemned = np.zeros_like(ground)
    for c in not_floor:
        condemned |= layout == c
    h, w = ground.shape
    if h < side or w < side:
        return np.zeros((0, 0), dtype=bool)

    def window(mask):
        acc = np.zeros((h + 1, w + 1), dtype=np.int32)
        acc[1:, 1:] = mask.astype(np.int32).cumsum(0).cumsum(1)
        return acc[side:, side:] - acc[:-side, side:] - acc[side:, :-side] + acc[:-side, :-side]

    if rule == "R1":
        return window(ground | condemned) == 0
    if rule == "R2":
        return window(~(ground | condemned)) > 0
    # R4: the ground condemns a tile on one pixel (a hole is a hole); a LEARNED colour condemns
    # only a tile made entirely of condemned colours — which is the evidence `_learn_refusal`
    # actually collects, since it only ever condemns from a tile of ONE FLAT COLOUR.
    return (window(ground) == 0) & (window(condemned) < side * side)


def reach(grid, start, deltas):
    """Cells the avatar can walk to from `start` over `grid`."""
    if not grid.size or start is None:
        return set()
    sy, sx = start
    if not (0 <= sy < grid.shape[0] and 0 <= sx < grid.shape[1]) or not grid[sy, sx]:
        return set()
    seen, stack = {start}, [start]
    while stack:
        y, x = stack.pop()
        for dy, dx in deltas:
            n = (y + dy, x + dx)
            if n in seen:
                continue
            if 0 <= n[0] < grid.shape[0] and 0 <= n[1] < grid.shape[1] and grid[n[0], n[1]]:
                seen.add(n)
                stack.append(n)
    return seen


class Watch:
    """The shipped agent, unmodified, with a read-only tap on the live tool."""

    def __init__(self, stride):
        self.agent = SE._make_agent("unified", game_id="dc22")
        self.stride = stride
        self.turn = 0
        self.l6 = 0
        self.level = None
        self.moves = []
        self.samples = []
        self.owners = {}
        self.summary = {"not_floor_ever": [], "negative_control_violations": 0,
                        "self_plan_not_zero": 0, "R1_reached": {}, "R4_reached": {}}

    def is_done(self, frames, obs):
        return self.agent.is_done(frames, obs)

    def choose_action(self, frames, obs):
        self.turn += 1
        lvl = int(obs.levels_completed)
        if self.level is None:
            self.level = lvl
        elif lvl != self.level:
            self.moves.append({"turn": self.turn, "from": self.level, "to": lvl,
                               "direction": "UP" if lvl > self.level else "DOWN"})
            self.level = lvl
        if lvl >= 5:
            self.l6 += 1
            cur = getattr(self.agent, "_current", None)
            self.owners[str(cur)] = self.owners.get(str(cur), 0) + 1
            if self.l6 == 1 or self.l6 % self.stride == 0:
                try:
                    self.sample(obs, cur)
                except Exception as exc:                      # noqa: BLE001
                    self.samples.append({"l6_turn": self.l6, "error": repr(exc)[:200]})
        return self.agent.choose_action(frames, obs)

    def sample(self, obs, cur):
        from admorphiq.tools.base import frame_2d
        t = self.agent.tools.get("gantry")
        if t is None:
            self.samples.append({"l6_turn": self.l6, "error": "no gantry in agent.tools",
                                 "names": sorted(self.agent.tools)})
            return
        g = frame_2d(obs)
        geom = t._read(g)
        rec = {"l6_turn": self.l6, "turn": self.turn, "owner": str(cur),
               "not_floor": sorted(int(c) for c in t._not_floor),
               "carry": list(t._carry) if t._carry else None,
               "rare": [int(v) for v in t._rare], "side": int(t._side),
               "avatar_colour": int(t._avatar), "marker_colour": int(t._marker),
               "dead": bool(t._dead), "retired": bool(t._retired),
               "kinds": {str(k): v for k, v in t._kind.items()},
               "drives": [list(c) for c in t._drives()],
               "objects": len(t._objects), "visited": len(t._visited),
               "group_periods": [int(g.get("period") or 0) for g in t._groups],
               "group_clicks": [list(g["click"]) for g in t._groups],
               "settled": bool(t._settled_model()),
               "warps": len(t._warps), "groups": len(t._groups),
               "steps_queued": len(t._steps), "stalls": int(t._stalls)}
        for c in rec["not_floor"]:
            if c not in self.summary["not_floor_ever"]:
                self.summary["not_floor_ever"].append(c)
        if geom is None:
            rec["read"] = None
            self.samples.append(rec)
            return
        board = np.asarray(geom["board"])
        top, panel_col = int(geom["top"]), int(geom["panel"])
        bg, side = int(geom["bg"]), int(geom["side"])
        rec["read"] = {"top": top, "bot": int(geom["bot"]), "panel_col": panel_col,
                       "board_shape": list(board.shape), "bg": bg,
                       "widened": bool(board.shape[1] > panel_col)}
        rec["panel_buttons"] = [list(c) for c in t._panel_buttons(g, geom)]
        start = t._at(board, t._avatar) if t._avatar >= 0 else None
        goal = t._at(board, t._marker) if t._marker >= 0 else None
        rec["avatar_cell"] = list(start) if start else None
        rec["marker_cell"] = list(goal) if goal else None
        deltas = list(t._deltas.values()) or [(side, 0), (-side, 0), (0, side), (0, -side)]
        cells = {n: (y - top, x) for n, (y, x) in L6_CELLS.items()}
        rec["tiles"] = {n: [[int(v) for v in row] for row in board[y:y + side, x:x + side]]
                        for n, (y, x) in cells.items()
                        if 0 <= y <= board.shape[0] - side and 0 <= x <= board.shape[1] - side}
        goals = {n: (y - top, x) for n, (y, x) in cells.items()}
        if goal:
            goals["marker"] = tuple(goal)
        if start:
            goals["self"] = tuple(start)          # negative control: must plan in 0 steps

        def ask():
            out = {}
            for n, c in goals.items():
                try:
                    plan = t._plan_full(board, tuple(start), {tuple(c)}) if start else []
                except Exception as exc:                       # noqa: BLE001
                    out[n] = "err:" + repr(exc)[:60]
                    continue
                out[n] = len(plan) if plan or tuple(c) == tuple(start) else None
            return out

        rec["plan_R1"] = ask()
        original = t._standable
        try:
            t._standable = lambda layout, _s=side, _b=bg, _t=t: standable(
                layout, _s, _b, _t._not_floor, "R4")
            rec["plan_R4"] = ask()
        finally:
            t._standable = original
        rec["rules"] = {}
        for rule in ("R1", "R4"):
            grid = standable(board, side, bg, t._not_floor, rule)
            r = reach(grid, tuple(start) if start else None, deltas)
            rec["rules"][rule] = {"standable": int(grid.sum()) if grid.size else 0,
                                  "walk_reach": len(r)}
        if not t._not_floor:
            if rec["plan_R1"] != rec["plan_R4"]:
                self.summary["negative_control_violations"] += 1
        if rec["plan_R1"].get("self") not in (0, None):
            self.summary["self_plan_not_zero"] = self.summary.get("self_plan_not_zero", 0) + 1
        for n, v in rec["plan_R1"].items():
            if v is not None and v != "self":
                self.summary.setdefault("R1_reached", {})[n] = True
        for n, v in rec["plan_R4"].items():
            if v is not None:
                self.summary.setdefault("R4_reached", {})[n] = True
        self.samples.append(rec)


def main():
    rep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    stride = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    w = Watch(stride)
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="l6live",
                      max_actions=4000, adapter_factory=lambda: w)
    print(json.dumps({
        "rep": rep, "stride": stride,
        "levels_completed": res.get("levels_completed"),
        "total_actions": res.get("total_actions"),
        "reproduces_banked": (res.get("levels_completed") == 5
                              and res.get("total_actions") == 925),
        "level_changes": w.moves,
        "l6_turns": w.l6, "owners_on_l6": w.owners,
        "summary": w.summary,
        "samples": w.samples,
    }), flush=True)


if __name__ == "__main__":
    main()
