"""dc22 level 6, watched on the SHIPPED run: what the LIVE tool believes, turn by turn.

Purpose. Two readings of this level are on the record and they disagree with each other.
Rule 7ak says the blocker is ours — `_solid`/`_standable` condemn an avatar-sized tile when ANY
pixel wears a condemned colour, and the crane's four plates are 2x2 sprites drawn `[[1,0],[0,C]]`
containing colour 0, which is condemned. A first attempt to reproduce that handed level 6 to a
FRESH `GantryCraneTool` and found `_not_floor` EMPTY — but a fresh tool is not the tool that plays
the game: `PhaseGridTool.__init__` sets `self._carry` OUTSIDE `reset()` on purpose, so the live
tool arrives at level 6 carrying the avatar/marker colour pair it has used since level 1, and
`_read` resolves the board differently because of it. Rule 7aj: reproduce the banked run first.

So this probe changes NOTHING about the run. It plays dc22 with the shipped unified agent for the
full budget and, on every turn from level 6 onward, reads the LIVE tool's own state out of
`agent.tools`. It must reproduce the banked 925 actions / 5 levels; if it does not, it is
describing a different run and nothing in it counts.

Reported per sampled turn: which tool the harness has the board on, `_not_floor`, the carried
pair, the avatar and marker cells, whether `_read` widened the board past the panel, the control
kinds and drives learned, and — under three standability rules (R1 any-bad = current,
R2 all-bad, R4 ground-any + condemned-all) — the standable count, the avatar's reachable region,
and whether the four crane plates and the two piyqze keys are inside it.

TWO CONTROLS, rule 7aj:
  * POSITIVE — `_not_floor` must be non-empty at some point on level 6 and the plate tiles must be
    REFUSED under R1 there. That is rule 7ak's claim; if it never happens the claim does not
    reproduce on the shipped run and says so.
  * NEGATIVE — while `_not_floor` is empty the three rules are identical BY CONSTRUCTION, and the
    probe reports the equality every turn. A difference there is a broken instrument.

Varying parameter FIRST = repetition index (the run is deterministic, so a fan measures a rate and
not a draw).  Second = sample stride in turns.  Prints ONE JSON line.
Rule 7f: any level change is reported with its DIRECTION and the resulting level number.
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
        self.summary = {"not_floor_ever": [], "plate_refused_R1_turns": 0,
                        "negative_control_violations": 0}

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
        rec["rules"] = {}
        for rule in ("R1", "R2", "R4"):
            grid = standable(board, side, bg, t._not_floor, rule)
            r = reach(grid, tuple(start) if start else None, deltas)
            rec["rules"][rule] = {
                "standable": int(grid.sum()) if grid.size else 0,
                "reach": len(r),
                "floor": {n: (bool(grid[y, x]) if grid.size and 0 <= y < grid.shape[0]
                              and 0 <= x < grid.shape[1] else None)
                          for n, (y, x) in cells.items()},
                "reachable": {n: (tuple(c) in r) for n, c in cells.items()},
            }
        if t._not_floor:
            if any(rec["rules"]["R1"]["floor"].get(f"plate_{k}") is False
                   for k in ("e_left", "b_up", "a_right", "h_down")):
                self.summary["plate_refused_R1_turns"] += 1
        else:
            # NEGATIVE CONTROL: nothing condemned means R1 and R4 are the same rule.
            if rec["rules"]["R1"]["standable"] != rec["rules"]["R4"]["standable"]:
                self.summary["negative_control_violations"] += 1
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
